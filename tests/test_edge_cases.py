"""Tests for edge cases identified during review."""
from __future__ import annotations

import pytest

from mcp_remote_ssh.session import SSHSession
from mcp_remote_ssh.server.execute import _build_env_prefix


class TestLongestFirstRedaction:
    """Verify secrets are redacted longest-first to prevent partial matches."""

    def test_longer_secret_redacted_before_shorter_substring(self):
        session = SSHSession(host='test-host')
        session._secrets = {
            'SHORT': 'abc',
            'LONG': 'abcdef',
        }
        text = 'value is abcdef here'
        redacted = session.redact(text)
        # 'abcdef' should be replaced as one unit, not 'abc' + 'def'
        assert redacted == 'value is *** here'

    def test_short_not_redacted_within_longer_already_redacted(self):
        session = SSHSession(host='test-host')
        session._secrets = {
            'TOKEN': 'supersecrettoken',
            'SHORT': 'secret',
        }
        text = 'found supersecrettoken in logs'
        redacted = session.redact(text)
        # 'supersecrettoken' replaced first, then 'secret' isn't a substring of '***'
        assert 'supersecrettoken' not in redacted
        assert 'secret' not in redacted

    def test_independent_secrets_both_redacted(self):
        session = SSHSession(host='test-host')
        session._secrets = {
            'A': 'alpha_value',
            'B': 'beta_value',
        }
        text = 'a=alpha_value b=beta_value'
        redacted = session.redact(text)
        assert redacted == 'a=*** b=***'


class TestEnvPrefixForExec:
    """Verify _build_env_prefix generates correct export statements."""

    def test_empty_when_no_secrets(self):
        session = SSHSession(host='test-host')
        assert _build_env_prefix(session) == ''

    def test_single_secret(self):
        session = SSHSession(host='test-host')
        session._secrets = {'TOKEN': 'abc123'}
        prefix = _build_env_prefix(session)
        assert 'export TOKEN=abc123' in prefix
        assert prefix.endswith(' && ')

    def test_multiple_secrets(self):
        session = SSHSession(host='test-host')
        session._secrets = {'A': 'val1', 'B': 'val2'}
        prefix = _build_env_prefix(session)
        assert 'export A=val1' in prefix
        assert 'export B=val2' in prefix
        assert prefix.endswith(' && ')

    def test_quotes_special_characters(self):
        session = SSHSession(host='test-host')
        session._secrets = {'PASS': "it's a p@ss!"}
        prefix = _build_env_prefix(session)
        # shlex.quote wraps with single quotes and escapes internal ones
        assert 'PASS=' in prefix
        assert "p@ss!" in prefix


class TestShellInjectionSafety:
    """Verify the heredoc injection pattern is safe."""

    def test_value_with_single_quotes(self):
        """shlex.quote must handle values containing single quotes."""
        import shlex
        value = "it's a test"
        quoted = shlex.quote(value)
        # shlex.quote handles internal single quotes by breaking out and using "'"
        assert quoted.startswith("'")
        # The quoted form must be non-empty and safe for bash
        assert len(quoted) > len(value)

    def test_value_with_newlines(self):
        """Values with newlines should be quoted safely."""
        import shlex
        value = "line1\nline2"
        quoted = shlex.quote(value)
        # shlex.quote handles this
        assert quoted  # non-empty

    def test_value_with_shell_metacharacters(self):
        """Shell metacharacters must not be interpreted."""
        import shlex
        value = "$(whoami) && rm -rf / ; echo pwned"
        quoted = shlex.quote(value)
        # Must be wrapped such that bash treats it as literal
        assert quoted.startswith("'")
        assert quoted.endswith("'")
