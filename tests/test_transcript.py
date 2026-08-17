"""Tests for the session transcript recording feature."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from mcp_remote_ssh.session import SSHSession, Transcript, TranscriptEntry


class TestTranscriptEntry:
    def test_to_dict_contains_all_fields(self):
        entry = TranscriptEntry(event='execute', data={'command': 'ls', 'exit_code': 0})
        d = entry.to_dict()
        assert d['event'] == 'execute'
        assert d['data']['command'] == 'ls'
        assert 'timestamp' in d
        assert 'time' in d

    def test_to_text_execute(self):
        entry = TranscriptEntry(
            event='execute',
            data={'command': 'whoami', 'stdout': 'root\n', 'stderr': '', 'exit_code': 0},
        )
        text = entry.to_text()
        assert '$ whoami' in text
        assert 'root' in text
        assert '[exit 0]' in text

    def test_to_text_shell_send(self):
        entry = TranscriptEntry(event='shell_send', data={'input': 'ls -la\n'})
        text = entry.to_text()
        assert '>> ls -la' in text

    def test_to_text_shell_read(self):
        entry = TranscriptEntry(event='shell_read', data={'output': 'total 42\n'})
        text = entry.to_text()
        assert 'total 42' in text

    def test_to_text_connect(self):
        entry = TranscriptEntry(event='connect', data={'host': 'myhost'})
        text = entry.to_text()
        assert '--- connect: myhost ---' in text

    def test_to_text_disconnect(self):
        entry = TranscriptEntry(event='disconnect', data={'host': 'myhost'})
        text = entry.to_text()
        assert '--- disconnect: myhost ---' in text


class TestTranscript:
    def test_recording_disabled_by_default(self):
        t = Transcript()
        assert not t.enabled
        t.record('execute', command='ls')
        assert len(t.entries) == 0

    def test_recording_when_enabled(self):
        t = Transcript()
        t.enabled = True
        t.record('execute', command='ls', exit_code=0)
        assert len(t.entries) == 1
        assert t.entries[0].event == 'execute'
        assert t.entries[0].data['command'] == 'ls'

    def test_multiple_entries(self):
        t = Transcript()
        t.enabled = True
        t.record('connect', host='h1')
        t.record('execute', command='ls')
        t.record('execute', command='pwd')
        assert len(t.entries) == 3

    def test_to_text(self):
        t = Transcript()
        t.enabled = True
        t.record('execute', command='whoami', stdout='root\n', stderr='', exit_code=0)
        text = t.to_text()
        assert '$ whoami' in text
        assert 'root' in text

    def test_to_jsonl(self):
        t = Transcript()
        t.enabled = True
        t.record('execute', command='ls', exit_code=0)
        t.record('execute', command='pwd', exit_code=0)
        jsonl = t.to_jsonl()
        lines = jsonl.strip().split('\n')
        assert len(lines) == 2
        parsed = json.loads(lines[0])
        assert parsed['event'] == 'execute'

    def test_save_text(self):
        t = Transcript()
        t.enabled = True
        t.record('execute', command='hostname', stdout='myhost\n', stderr='', exit_code=0)
        with tempfile.NamedTemporaryFile(suffix='.log', delete=False) as f:
            path = f.name
        count = t.save(path, fmt='text')
        assert count == 1
        content = Path(path).read_text()
        assert '$ hostname' in content
        Path(path).unlink()

    def test_save_jsonl(self):
        t = Transcript()
        t.enabled = True
        t.record('connect', host='h1')
        t.record('execute', command='ls', exit_code=0)
        with tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False) as f:
            path = f.name
        count = t.save(path, fmt='jsonl')
        assert count == 2
        lines = Path(path).read_text().strip().split('\n')
        assert len(lines) == 2
        Path(path).unlink()

    def test_clear(self):
        t = Transcript()
        t.enabled = True
        t.record('execute', command='a')
        t.record('execute', command='b')
        cleared = t.clear()
        assert cleared == 2
        assert len(t.entries) == 0


class TestSSHSessionTranscript:
    def test_session_has_transcript(self):
        s = SSHSession(host='test-host')
        assert hasattr(s, 'transcript')
        assert isinstance(s.transcript, Transcript)
        assert not s.transcript.enabled

    def test_summary_includes_recording_fields(self):
        s = SSHSession(host='test-host')
        summary = s.summary()
        assert 'recording' in summary
        assert 'transcript_entries' in summary
        assert summary['recording'] is False
        assert summary['transcript_entries'] == 0

    def test_summary_reflects_enabled_state(self):
        s = SSHSession(host='test-host')
        s.transcript.enabled = True
        s.transcript.record('execute', command='test')
        summary = s.summary()
        assert summary['recording'] is True
        assert summary['transcript_entries'] == 1


class TestDefaultPathNoRecording:
    """Verify that when recording is disabled (the default), existing code
    paths produce zero transcript entries — no new code is entered."""

    @pytest.fixture
    def session(self):
        return SSHSession(host='test-host', username='root')

    def test_shell_send_no_recording(self, session):
        """shell_send must not record when transcript is disabled."""
        channel = MagicMock()
        channel.closed = False
        session._shell_channel = channel
        assert not session.transcript.enabled

        session.shell_send('ls -la\n')

        channel.sendall.assert_called_once_with(b'ls -la\n')
        assert len(session.transcript.entries) == 0

    def test_shell_read_no_recording(self, session):
        """shell_read must not record when transcript is disabled."""
        channel = MagicMock()
        channel.closed = False
        channel.recv_ready.side_effect = [True, False]
        channel.recv.return_value = b'output data'
        session._shell_channel = channel
        assert not session.transcript.enabled

        result = session.shell_read()

        assert result == 'output data'
        assert len(session.transcript.entries) == 0

    def test_shell_read_empty_no_recording(self, session):
        """shell_read returning empty data must not record."""
        channel = MagicMock()
        channel.closed = False
        channel.recv_ready.return_value = False
        session._shell_channel = channel

        result = session.shell_read()

        assert result == ''
        assert len(session.transcript.entries) == 0

    def test_transcript_stays_empty_after_many_operations(self, session):
        """Multiple shell sends and reads with recording off produce zero entries."""
        channel = MagicMock()
        channel.closed = False
        channel.recv_ready.side_effect = [True, False, True, False, True, False]
        channel.recv.return_value = b'data'
        session._shell_channel = channel

        session.shell_send('cmd1\n')
        session.shell_read()
        session.shell_send('cmd2\n')
        session.shell_read()
        session.shell_send('cmd3\n')
        session.shell_read()

        assert len(session.transcript.entries) == 0


class TestEnabledPathRecording:
    """Verify that when recording IS enabled, all injection points
    correctly capture transcript entries."""

    @pytest.fixture
    def session(self):
        s = SSHSession(host='test-host', username='root')
        s.transcript.enabled = True
        return s

    def test_shell_send_records(self, session):
        channel = MagicMock()
        channel.closed = False
        session._shell_channel = channel

        session.shell_send('whoami\n')

        assert len(session.transcript.entries) == 1
        entry = session.transcript.entries[0]
        assert entry.event == 'shell_send'
        assert entry.data['input'] == 'whoami\n'

    def test_shell_read_records_nonempty(self, session):
        channel = MagicMock()
        channel.closed = False
        channel.recv_ready.side_effect = [True, False]
        channel.recv.return_value = b'root\n'
        session._shell_channel = channel

        result = session.shell_read()

        assert result == 'root\n'
        assert len(session.transcript.entries) == 1
        assert session.transcript.entries[0].event == 'shell_read'
        assert session.transcript.entries[0].data['output'] == 'root\n'

    def test_shell_read_skips_empty(self, session):
        """Even with recording on, empty reads should not create entries."""
        channel = MagicMock()
        channel.closed = False
        channel.recv_ready.return_value = False
        session._shell_channel = channel

        result = session.shell_read()

        assert result == ''
        assert len(session.transcript.entries) == 0

    def test_send_read_interleaved(self, session):
        """A send+read cycle should produce exactly 2 entries."""
        channel = MagicMock()
        channel.closed = False
        channel.recv_ready.side_effect = [True, False]
        channel.recv.return_value = b'output'
        session._shell_channel = channel

        session.shell_send('hostname\n')
        session.shell_read()

        assert len(session.transcript.entries) == 2
        assert session.transcript.entries[0].event == 'shell_send'
        assert session.transcript.entries[1].event == 'shell_read'

    def test_toggle_recording_midstream(self):
        """Entries only accumulate while enabled; disabling stops new entries."""
        s = SSHSession(host='test-host')
        channel = MagicMock()
        channel.closed = False
        channel.recv_ready.side_effect = [True, False, True, False]
        channel.recv.return_value = b'data'
        s._shell_channel = channel

        s.shell_send('before\n')
        assert len(s.transcript.entries) == 0

        s.transcript.enabled = True
        s.shell_send('during\n')
        s.shell_read()
        assert len(s.transcript.entries) == 2

        s.transcript.enabled = False
        s.shell_send('after\n')
        s.shell_read()
        assert len(s.transcript.entries) == 2

    def test_recorded_entries_persist_after_disable(self):
        """Disabling recording does not clear existing entries."""
        s = SSHSession(host='test-host')
        s.transcript.enabled = True
        s.transcript.record('execute', command='ls')
        s.transcript.record('execute', command='pwd')

        s.transcript.enabled = False
        assert len(s.transcript.entries) == 2
        assert s.transcript.entries[0].data['command'] == 'ls'

    def test_transcript_text_output_order(self, session):
        """Text output preserves chronological order."""
        channel = MagicMock()
        channel.closed = False
        channel.recv_ready.side_effect = [True, False, True, False]
        channel.recv.side_effect = [b'out1', b'out2']
        session._shell_channel = channel

        session.shell_send('cmd1\n')
        session.shell_read()
        session.shell_send('cmd2\n')
        session.shell_read()

        text = session.transcript.to_text()
        lines = text.split('\n')
        send_lines = [line for line in lines if '>>' in line]
        assert 'cmd1' in send_lines[0]
        assert 'cmd2' in send_lines[1]

    def test_session_close_preserves_transcript(self):
        """Closing a session does not destroy the transcript object."""
        s = SSHSession(host='test-host')
        s.transcript.enabled = True
        s.transcript.record('execute', command='test')
        s.close()
        assert len(s.transcript.entries) == 1


class TestTranscriptWithRedaction:
    """Verify that secrets loaded into a session do not leak into transcripts."""

    def test_execute_transcript_is_redacted(self):
        """Simulates what ssh_execute does: redact before recording."""
        s = SSHSession(host='test-host')
        s._secrets = {'TOKEN': 'supersecret123'}
        s.transcript.enabled = True

        stdout = s.redact('Using token supersecret123 for auth')
        stderr = s.redact('')
        s.transcript.record('execute', command='curl -H ...', stdout=stdout, stderr=stderr, exit_code=0)

        entry = s.transcript.entries[0]
        assert 'supersecret123' not in entry.data['stdout']
        assert '***' in entry.data['stdout']
        assert 'supersecret123' not in entry.to_text()

    def test_shell_send_with_secret_in_command(self):
        """Shell input is redacted before recording so ssh_get_transcript
        cannot leak loaded secrets back to the LLM."""
        s = SSHSession(host='test-host')
        s._secrets = {'PASS': 'hunter2'}
        s.transcript.enabled = True
        channel = MagicMock()
        channel.closed = False
        s._shell_channel = channel

        s.shell_send('echo hunter2\n')

        entry = s.transcript.entries[0]
        assert 'hunter2' not in entry.data['input']
        assert entry.data['input'] == 'echo ***\n'

    def test_shell_read_output_is_redacted(self):
        s = SSHSession(host='test-host')
        s._secrets = {'TOKEN': 'supersecret123'}
        s.transcript.enabled = True
        channel = MagicMock()
        channel.closed = False
        channel.recv_ready.side_effect = [True, False]
        channel.recv.return_value = b'Using token supersecret123\n'
        s._shell_channel = channel

        result = s.shell_read()

        assert 'supersecret123' in result  # raw channel data is unchanged
        assert 'supersecret123' not in s.transcript.entries[0].data['output']
        assert '***' in s.transcript.entries[0].data['output']


class TestTranscriptTools:
    """MCP tool wrappers around Transcript (no live SSH)."""

    @pytest.fixture
    def session(self):
        s = SSHSession(host='test-host', username='root')
        mock_transport = MagicMock()
        mock_transport.is_active.return_value = True
        s.client = MagicMock()
        s.client.get_transport.return_value = mock_transport
        return s

    @pytest.fixture
    def mock_ctx(self, session):
        ctx = MagicMock()
        ctx.request_context.lifespan_context.sessions.get.return_value = session
        return ctx

    @pytest.mark.asyncio
    async def test_start_and_stop_recording(self, session, mock_ctx):
        from mcp_remote_ssh.server.transcript import ssh_start_recording, ssh_stop_recording

        started = await ssh_start_recording(mock_ctx, session.session_id)
        assert 'Recording started' in started
        assert session.transcript.enabled
        assert session.transcript.entries[0].event == 'recording_started'

        already = await ssh_start_recording(mock_ctx, session.session_id)
        assert 'already recording' in already
        assert sum(1 for e in session.transcript.entries if e.event == 'recording_started') == 1

        stopped = await ssh_stop_recording(mock_ctx, session.session_id)
        assert 'Recording stopped' in stopped
        assert not session.transcript.enabled
        assert session.transcript.entries[-1].event == 'recording_stopped'

        idle = await ssh_stop_recording(mock_ctx, session.session_id)
        assert 'is not recording' in idle

    @pytest.mark.asyncio
    async def test_get_transcript_text_jsonl_and_last_n(self, session, mock_ctx):
        from mcp_remote_ssh.server.transcript import ssh_get_transcript, ssh_start_recording

        await ssh_start_recording(mock_ctx, session.session_id)
        session.transcript.record('execute', command='one', stdout='a\n', stderr='', exit_code=0)
        session.transcript.record('execute', command='two', stdout='b\n', stderr='', exit_code=0)

        text = await ssh_get_transcript(mock_ctx, session.session_id, fmt='text')
        assert text['recording'] is True
        assert text['total_entries'] == 3  # recording_started + two executes
        assert '$ one' in text['transcript']
        assert '$ two' in text['transcript']

        jsonl = await ssh_get_transcript(mock_ctx, session.session_id, fmt='jsonl')
        lines = [ln for ln in jsonl['transcript'].split('\n') if ln]
        assert len(lines) == 3
        parsed = json.loads(lines[-1])
        assert parsed['event'] == 'execute'
        assert parsed['data']['command'] == 'two'

        tail = await ssh_get_transcript(mock_ctx, session.session_id, last_n=1)
        assert tail['returned_entries'] == 1
        assert '$ two' in tail['transcript']
        assert '$ one' not in tail['transcript']

    @pytest.mark.asyncio
    async def test_save_transcript_is_local_only(self, session, mock_ctx, tmp_path):
        from mcp_remote_ssh.server.transcript import ssh_save_transcript, ssh_start_recording

        await ssh_start_recording(mock_ctx, session.session_id)
        session.transcript.record('execute', command='hostname', stdout='testhost\n', stderr='', exit_code=0)
        session._sftp = MagicMock()
        path = tmp_path / 'nested' / 'session.log'
        result = await ssh_save_transcript(mock_ctx, session.session_id, str(path))
        assert str(path) in result
        assert path.read_text().count('$ hostname') == 1
        session._sftp.open.assert_not_called()

    @pytest.mark.asyncio
    async def test_ssh_execute_records_when_enabled(self, session, mock_ctx):
        from mcp_remote_ssh.server.execute import ssh_execute

        session.transcript.enabled = True
        stdout = MagicMock()
        stdout.read.return_value = b'hello\n'
        stdout.channel.recv_exit_status.return_value = 0
        stderr = MagicMock()
        stderr.read.return_value = b''
        session.client.exec_command.return_value = (MagicMock(), stdout, stderr)

        result = await ssh_execute(mock_ctx, session.session_id, 'echo hello')
        assert result['exit_code'] == 0
        assert result['stdout'] == 'hello\n'
        assert len(session.transcript.entries) == 1
        assert session.transcript.entries[0].event == 'execute'
        assert session.transcript.entries[0].data['command'] == 'echo hello'
        assert session.transcript.entries[0].data['stdout'] == 'hello\n'

    @pytest.mark.asyncio
    async def test_ssh_execute_does_not_record_when_disabled(self, session, mock_ctx):
        from mcp_remote_ssh.server.execute import ssh_execute

        stdout = MagicMock()
        stdout.read.return_value = b'hello\n'
        stdout.channel.recv_exit_status.return_value = 0
        stderr = MagicMock()
        stderr.read.return_value = b''
        session.client.exec_command.return_value = (MagicMock(), stdout, stderr)

        await ssh_execute(mock_ctx, session.session_id, 'echo hello')
        assert len(session.transcript.entries) == 0

    @pytest.mark.asyncio
    async def test_ssh_execute_redacts_before_recording(self, session, mock_ctx):
        from mcp_remote_ssh.server.execute import ssh_execute

        session._secrets = {'TOKEN': 'supersecret123'}
        session.transcript.enabled = True
        stdout = MagicMock()
        stdout.read.return_value = b'Using token supersecret123 for auth\n'
        stdout.channel.recv_exit_status.return_value = 0
        stderr = MagicMock()
        stderr.read.return_value = b''
        session.client.exec_command.return_value = (MagicMock(), stdout, stderr)

        result = await ssh_execute(mock_ctx, session.session_id, 'curl -H ...')
        assert 'supersecret123' not in result['stdout']
        assert 'supersecret123' not in session.transcript.entries[0].data['stdout']
        assert '***' in session.transcript.entries[0].data['stdout']

    @pytest.mark.asyncio
    async def test_ssh_sudo_execute_records_sudo_prefix(self, session, mock_ctx):
        from mcp_remote_ssh.server.execute import ssh_sudo_execute

        session.transcript.enabled = True
        stdout = MagicMock()
        stdout.read.return_value = b'ok\n'
        stdout.channel.recv_exit_status.return_value = 0
        stderr = MagicMock()
        stderr.read.return_value = b''
        session.client.exec_command.return_value = (MagicMock(), stdout, stderr)

        await ssh_sudo_execute(mock_ctx, session.session_id, 'systemctl status sshd')
        assert session.transcript.entries[0].data['command'] == 'sudo systemctl status sshd'
