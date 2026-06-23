"""Tests for ssh_load_env_file reading from LOCAL filesystem."""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_remote_ssh.server.secrets import _parse_env_content, ssh_load_env_file
from mcp_remote_ssh.session import SSHSession


class TestLoadEnvFromLocalFile:
    """Verify the tool reads from the local filesystem, not the remote host."""

    @pytest.fixture
    def env_file(self, tmp_path):
        """Create a real local env file."""
        f = tmp_path / 'secrets.env'
        f.write_text(
            'TOKEN=local_secret_abc\n'
            'DB_PASS=hunter2\n'
            '# comment\n'
            'API_KEY="quoted_key_123"\n'
        )
        return f

    @pytest.fixture
    def session(self):
        s = SSHSession(host='remote-host', username='root')
        # Mock the transport so is_connected returns True
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
    async def test_reads_local_file(self, env_file, session, mock_ctx):
        result = await ssh_load_env_file(mock_ctx, session.session_id, str(env_file))
        assert 'TOKEN' in result
        assert 'DB_PASS' in result
        assert 'API_KEY' in result
        assert 'local_secret_abc' not in result
        assert 'hunter2' not in result
        assert 'quoted_key_123' not in result

    @pytest.mark.asyncio
    async def test_secrets_stored_in_session(self, env_file, session, mock_ctx):
        await ssh_load_env_file(mock_ctx, session.session_id, str(env_file))
        assert session._secrets['TOKEN'] == 'local_secret_abc'
        assert session._secrets['DB_PASS'] == 'hunter2'
        assert session._secrets['API_KEY'] == 'quoted_key_123'

    @pytest.mark.asyncio
    async def test_file_not_found(self, session, mock_ctx):
        result = await ssh_load_env_file(mock_ctx, session.session_id, '/nonexistent/path.env')
        assert 'not found' in result.lower()

    @pytest.mark.asyncio
    async def test_empty_file(self, tmp_path, session, mock_ctx):
        f = tmp_path / 'empty.env'
        f.write_text('# only comments\n\n')
        result = await ssh_load_env_file(mock_ctx, session.session_id, str(f))
        assert 'No KEY=VALUE' in result

    @pytest.mark.asyncio
    async def test_redaction_works_after_load(self, env_file, session, mock_ctx):
        await ssh_load_env_file(mock_ctx, session.session_id, str(env_file))
        output = 'Connected with token local_secret_abc successfully'
        redacted = session.redact(output)
        assert 'local_secret_abc' not in redacted
        assert '***' in redacted

    @pytest.mark.asyncio
    async def test_does_not_read_remote_file(self, env_file, session, mock_ctx):
        """Verify SFTP is never called -- the file is local only."""
        session._sftp = MagicMock()
        await ssh_load_env_file(mock_ctx, session.session_id, str(env_file))
        session._sftp.open.assert_not_called()

    @pytest.mark.asyncio
    async def test_tilde_expansion(self, tmp_path, session, mock_ctx, monkeypatch):
        """Test that ~ in path gets expanded."""
        f = tmp_path / 'secrets.env'
        f.write_text('VAR=value\n')
        monkeypatch.setenv('HOME', str(tmp_path))
        result = await ssh_load_env_file(mock_ctx, session.session_id, '~/secrets.env')
        assert 'VAR' in result
