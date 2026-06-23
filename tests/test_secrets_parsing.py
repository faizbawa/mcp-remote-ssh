"""Tests for env file parsing logic."""
from __future__ import annotations

from mcp_remote_ssh.server.secrets import _parse_env_content


class TestParseEnvContent:
    def test_basic_key_value(self):
        content = 'TOKEN=abc123\nDB=mydb\n'
        result = _parse_env_content(content)
        assert result == {'TOKEN': 'abc123', 'DB': 'mydb'}

    def test_ignores_comments(self):
        content = '# this is a comment\nTOKEN=abc123\n# another comment\n'
        result = _parse_env_content(content)
        assert result == {'TOKEN': 'abc123'}

    def test_ignores_empty_lines(self):
        content = '\n\nTOKEN=abc123\n\n\nDB=mydb\n\n'
        result = _parse_env_content(content)
        assert result == {'TOKEN': 'abc123', 'DB': 'mydb'}

    def test_strips_double_quotes(self):
        content = 'TOKEN="my_secret_value"\n'
        result = _parse_env_content(content)
        assert result == {'TOKEN': 'my_secret_value'}

    def test_strips_single_quotes(self):
        content = "TOKEN='my_secret_value'\n"
        result = _parse_env_content(content)
        assert result == {'TOKEN': 'my_secret_value'}

    def test_handles_export_prefix(self):
        content = 'export TOKEN=abc123\nexport DB=mydb\n'
        result = _parse_env_content(content)
        assert result == {'TOKEN': 'abc123', 'DB': 'mydb'}

    def test_value_with_equals_sign(self):
        content = 'CONNECTION_STRING=host=localhost;port=5432\n'
        result = _parse_env_content(content)
        assert result == {'CONNECTION_STRING': 'host=localhost;port=5432'}

    def test_empty_value(self):
        content = 'EMPTY_VAR=\n'
        result = _parse_env_content(content)
        assert result == {'EMPTY_VAR': ''}

    def test_value_with_spaces(self):
        content = 'MSG="hello world"\n'
        result = _parse_env_content(content)
        assert result == {'MSG': 'hello world'}

    def test_invalid_key_ignored(self):
        content = '123INVALID=value\nVALID_KEY=value\n'
        result = _parse_env_content(content)
        assert result == {'VALID_KEY': 'value'}

    def test_full_env_file(self, env_file_content, parsed_secrets):
        result = _parse_env_content(env_file_content)
        assert result == parsed_secrets

    def test_empty_content(self):
        assert _parse_env_content('') == {}
        assert _parse_env_content('# only comments\n# here\n') == {}

    def test_no_trailing_newline(self):
        content = 'TOKEN=abc123'
        result = _parse_env_content(content)
        assert result == {'TOKEN': 'abc123'}

    def test_windows_line_endings(self):
        content = 'TOKEN=abc123\r\nDB=mydb\r\n'
        result = _parse_env_content(content)
        assert result == {'TOKEN': 'abc123', 'DB': 'mydb'}
