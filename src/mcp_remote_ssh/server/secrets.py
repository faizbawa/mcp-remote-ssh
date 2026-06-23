from __future__ import annotations

import asyncio
import re
import shlex
from pathlib import Path

from fastmcp import Context
from loguru import logger

from mcp_remote_ssh.server import mcp
from mcp_remote_ssh.server.helpers import get_session, require_connected

_ENV_LINE_RE = re.compile(
    r'^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$'
)


def _parse_env_content(content: str) -> dict[str, str]:
    """Parse KEY=VALUE lines from env file content. Handles quoting."""
    result: dict[str, str] = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        m = _ENV_LINE_RE.match(line)
        if m:
            key = m.group(1)
            value = m.group(2)
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            result[key] = value
    return result


@mcp.tool()
async def ssh_load_env_file(
    ctx: Context,
    session_id: str,
    file_path: str,
) -> str:
    """Load environment variables from a LOCAL file (on the machine running
    this MCP server) into the remote SSH session.

    The file is read from the local filesystem -- it does NOT need to exist
    on the remote host. Variable VALUES are never returned to the caller;
    only variable names are confirmed.

    Loaded values are:
    1. Registered for automatic redaction -- any subsequent tool output
       (ssh_execute, ssh_shell_send, ssh_shell_read, ssh_read_remote_file)
       that contains a secret value will have it replaced with '***'.
    2. Exported into the remote shell (if open) via builtins, avoiding
       exposure in the process tree on the remote host.

    Args:
        session_id: The session ID returned by ssh_connect.
        file_path: Absolute path to the env file on the LOCAL machine
                   (where this MCP server is running).

    Returns:
        Confirmation with variable names (never values).
    """
    session = get_session(ctx, session_id)
    require_connected(session)

    local_file = Path(file_path).expanduser()
    if not local_file.exists():
        return f'File not found (local): {file_path}'
    if not local_file.is_file():
        return f'Not a file (local): {file_path}'

    try:
        content = local_file.read_text(encoding='utf-8')
    except PermissionError:
        return f'Permission denied reading (local): {file_path}'

    secrets = _parse_env_content(content)
    if not secrets:
        return f'No KEY=VALUE pairs found in {file_path}'

    # Store in the redaction registry
    session._secrets.update(secrets)
    logger.info(
        f'[{session_id}] Loaded {len(secrets)} secrets from local file {file_path}: '
        f'{", ".join(secrets.keys())}'
    )

    # If a shell is open, inject into the remote session via builtins
    # Using heredoc + read: no fork, value never in /proc/*/cmdline
    if session.has_shell:
        loop = asyncio.get_running_loop()
        for key, value in secrets.items():
            cmd = f'read -r {key} <<< {shlex.quote(value)} && export {key}\n'
            await loop.run_in_executor(None, lambda c=cmd: session.shell_send(c))
        await asyncio.sleep(0.5)
        # Drain buffer silently (don't return it to caller)
        await loop.run_in_executor(None, lambda: session.shell_read())

    var_names = ', '.join(secrets.keys())
    return f'Loaded {len(secrets)} variables from local:{file_path}: {var_names}'


@mcp.tool()
async def ssh_clear_secrets(
    ctx: Context,
    session_id: str,
) -> str:
    """Clear all loaded secrets from the redaction registry. Secrets will
    no longer be redacted from tool output. Does NOT unset the environment
    variables from the remote shell.

    Args:
        session_id: The session ID returned by ssh_connect.

    Returns:
        Confirmation message.
    """
    session = get_session(ctx, session_id)
    count = len(session._secrets)
    session._secrets.clear()
    logger.info(f'[{session_id}] Cleared {count} secrets from redaction registry')
    return f'Cleared {count} secrets from redaction registry.'
