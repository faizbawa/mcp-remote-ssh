from __future__ import annotations

import pytest


@pytest.fixture
def env_file_content():
    """Sample .env file content for testing."""
    return (
        '# Database config\n'
        'DB_HOST=localhost\n'
        'DB_PASSWORD=super_secret_123\n'
        'API_TOKEN="bearer_token_abc789"\n'
        "SECRET_KEY='single_quoted_value'\n"
        '\n'
        '# Empty and comment lines should be skipped\n'
        'export EXPORTED_VAR=exported_value\n'
    )


@pytest.fixture
def parsed_secrets():
    """Expected parsed secrets from the sample env file."""
    return {
        'DB_HOST': 'localhost',
        'DB_PASSWORD': 'super_secret_123',
        'API_TOKEN': 'bearer_token_abc789',
        'SECRET_KEY': 'single_quoted_value',
        'EXPORTED_VAR': 'exported_value',
    }
