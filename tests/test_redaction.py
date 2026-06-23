"""Tests for the SSHSession redaction mechanism."""
from __future__ import annotations

import pytest

from mcp_remote_ssh.session import SSHSession


class TestRedaction:
    @pytest.fixture
    def session(self):
        """Create an SSHSession with pre-loaded secrets."""
        s = SSHSession(host='test-host', username='root')
        s._secrets = {
            'TOKEN': 'abc123secret',
            'DB_PASS': 'p@ssw0rd!',
            'API_KEY': 'sk-1234567890abcdef',
        }
        return s

    def test_redacts_single_secret(self, session):
        text = 'Your token is abc123secret'
        assert session.redact(text) == 'Your token is ***'

    def test_redacts_multiple_secrets(self, session):
        text = 'token=abc123secret password=p@ssw0rd!'
        result = session.redact(text)
        assert 'abc123secret' not in result
        assert 'p@ssw0rd!' not in result
        assert result == 'token=*** password=***'

    def test_redacts_secret_appearing_multiple_times(self, session):
        text = 'first: abc123secret and again: abc123secret'
        result = session.redact(text)
        assert 'abc123secret' not in result
        assert result == 'first: *** and again: ***'

    def test_no_redaction_without_secrets(self):
        session = SSHSession(host='test-host')
        text = 'some normal output with no secrets'
        assert session.redact(text) == text

    def test_no_redaction_when_no_match(self, session):
        text = 'this text contains no secret values at all'
        assert session.redact(text) == text

    def test_redacts_in_multiline_output(self, session):
        text = (
            'Connecting to API...\n'
            'Authorization: Bearer abc123secret\n'
            'Response: 200 OK\n'
        )
        result = session.redact(text)
        assert 'abc123secret' not in result
        assert 'Authorization: Bearer ***' in result

    def test_redacts_special_characters_in_secret(self, session):
        text = 'DB connection with password p@ssw0rd! established'
        result = session.redact(text)
        assert 'p@ssw0rd!' not in result

    def test_empty_secret_value_not_redacted(self):
        """Empty string secrets should not cause all text to be replaced."""
        session = SSHSession(host='test-host')
        session._secrets = {'EMPTY': ''}
        text = 'some normal text'
        assert session.redact(text) == text

    def test_redacts_in_env_dump(self, session):
        text = (
            'TOKEN=abc123secret\n'
            'DB_PASS=p@ssw0rd!\n'
            'API_KEY=sk-1234567890abcdef\n'
            'PATH=/usr/bin:/bin\n'
        )
        result = session.redact(text)
        assert 'abc123secret' not in result
        assert 'p@ssw0rd!' not in result
        assert 'sk-1234567890abcdef' not in result
        assert 'PATH=/usr/bin:/bin' in result

    def test_redaction_preserves_surrounding_context(self, session):
        text = '[INFO] Using API key: sk-1234567890abcdef for auth'
        result = session.redact(text)
        assert result == '[INFO] Using API key: *** for auth'

    def test_secrets_can_be_added_incrementally(self):
        session = SSHSession(host='test-host')
        text = 'secret1 and secret2'

        session._secrets['A'] = 'secret1'
        assert session.redact(text) == '*** and secret2'

        session._secrets['B'] = 'secret2'
        assert session.redact(text) == '*** and ***'

    def test_clear_secrets_stops_redaction(self):
        session = SSHSession(host='test-host')
        session._secrets = {'TOKEN': 'mysecret'}
        assert session.redact('value is mysecret') == 'value is ***'

        session._secrets.clear()
        assert session.redact('value is mysecret') == 'value is mysecret'
