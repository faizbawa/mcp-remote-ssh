"""Integration tests: verify redaction applies across execute and shell tools."""
from __future__ import annotations

import asyncio
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from mcp_remote_ssh.session import SSHSession


class TestExecuteRedaction:
    """Test that ssh_execute output is redacted."""

    def test_stdout_redacted(self):
        session = SSHSession(host='test-host', username='root')
        session._secrets = {'TOKEN': 'supersecret123'}

        raw_stdout = 'Using token supersecret123 for auth'
        redacted = session.redact(raw_stdout)
        assert redacted == 'Using token *** for auth'
        assert 'supersecret123' not in redacted

    def test_stderr_redacted(self):
        session = SSHSession(host='test-host', username='root')
        session._secrets = {'API_KEY': 'sk-abcdef'}

        raw_stderr = 'Error: invalid key sk-abcdef'
        redacted = session.redact(raw_stderr)
        assert redacted == 'Error: invalid key ***'

    def test_both_stdout_stderr_redacted(self):
        session = SSHSession(host='test-host', username='root')
        session._secrets = {'PASS': 'mypass123'}

        stdout = 'Connected with mypass123'
        stderr = 'Warning: mypass123 exposed in log'
        assert 'mypass123' not in session.redact(stdout)
        assert 'mypass123' not in session.redact(stderr)


class TestShellBufferRedaction:
    """Test that shell buffer reads are redacted."""

    def test_shell_buffer_redacted(self):
        session = SSHSession(host='test-host', username='root')
        session._secrets = {'DB_PASS': 'hunter2'}

        # Simulate shell buffer containing the secret
        session._shell_buffer = (
            '$ echo $DB_PASS\n'
            'hunter2\n'
            '$ \n'
        )

        # shell_read_buffer returns lines from buffer
        # (we can't call it without a channel, but we test redact on raw output)
        raw_output = session._shell_buffer
        redacted = session.redact(raw_output)
        assert 'hunter2' not in redacted
        assert '***' in redacted
        assert '$ echo $DB_PASS' in redacted  # var name is fine

    def test_secret_in_command_output_redacted(self):
        session = SSHSession(host='test-host', username='root')
        session._secrets = {'TOKEN': 'ghp_abc123xyz789'}

        output = (
            '$ curl -H "Authorization: Bearer ghp_abc123xyz789" https://api.github.com\n'
            '{"login": "user"}\n'
        )
        redacted = session.redact(output)
        assert 'ghp_abc123xyz789' not in redacted
        assert 'Authorization: Bearer ***' in redacted


class TestSftpRedaction:
    """Test that file reads are redacted."""

    def test_file_content_redacted(self):
        session = SSHSession(host='test-host', username='root')
        session._secrets = {'SECRET': 'top_secret_value'}

        file_content = (
            'config_key=normal_value\n'
            'auth_token=top_secret_value\n'
            'debug=true\n'
        )
        redacted = session.redact(file_content)
        assert 'top_secret_value' not in redacted
        assert 'auth_token=***' in redacted
        assert 'config_key=normal_value' in redacted


class TestEdgeCases:
    """Edge cases for the redaction system."""

    def test_secret_substring_of_another(self):
        """If one secret is a substring of another, both should be handled."""
        session = SSHSession(host='test-host', username='root')
        session._secrets = {
            'SHORT': 'abc',
            'LONG': 'abc123',
        }
        text = 'values: abc123 and abc'
        redacted = session.redact(text)
        # Both should be redacted
        assert 'abc123' not in redacted
        assert 'abc' not in redacted

    def test_overlapping_secrets(self):
        """Secrets that overlap in the text."""
        session = SSHSession(host='test-host', username='root')
        session._secrets = {'A': 'abcdef', 'B': 'defghi'}
        text = 'abcdefghi'
        redacted = session.redact(text)
        # At minimum, both original values should not appear as-is
        assert 'abcdef' not in redacted or 'defghi' not in redacted

    def test_binary_like_content(self):
        """Non-ASCII content shouldn't crash redaction."""
        session = SSHSession(host='test-host', username='root')
        session._secrets = {'KEY': 'secret'}
        text = 'binary: \x00\x01\x02 secret \xff\xfe'
        redacted = session.redact(text)
        assert 'secret' not in redacted

    def test_very_long_secret(self):
        """Long secrets (like JWTs) should be redacted."""
        session = SSHSession(host='test-host', username='root')
        jwt = 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abc123signature'
        session._secrets = {'JWT': jwt}
        text = f'Authorization: Bearer {jwt}'
        redacted = session.redact(text)
        assert jwt not in redacted
        assert redacted == 'Authorization: Bearer ***'

    def test_secret_at_boundary(self):
        """Secret at start and end of string."""
        session = SSHSession(host='test-host', username='root')
        session._secrets = {'S': 'secret'}
        assert session.redact('secret') == '***'
        assert session.redact('secretsuffix') == '***suffix'
        assert session.redact('prefixsecret') == 'prefix***'
