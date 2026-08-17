from __future__ import annotations

import asyncio
import shlex
from typing import Any

from fastmcp import Context
from loguru import logger

from mcp_remote_ssh.server import mcp
from mcp_remote_ssh.server.helpers import get_session, require_connected


def _build_env_script(session) -> str:
    """Build export statements for secrets, to be fed via stdin.
    Never appears in /proc/*/cmdline."""
    if not session._secrets:
        return ''
    lines = []
    for key, value in session._secrets.items():
        lines.append(f'export {key}={shlex.quote(value)}')
    return '\n'.join(lines) + '\n'


@mcp.tool()
async def ssh_execute(
    ctx: Context,
    session_id: str,
    command: str,
    timeout: int = 120,
) -> dict[str, Any]:
    """Execute a command on the remote host and return structured output.
    Each call runs in an independent exec channel -- no state is shared
    between calls (use ssh_shell_* tools for persistent state).

    If secrets have been loaded via ssh_load_env_file, they are automatically
    injected as environment variables for this command.

    Args:
        session_id: The session ID returned by ssh_connect.
        command: Shell command to execute.
        timeout: Maximum seconds to wait for the command to finish (default: 120).

    Returns:
        Dict with stdout, stderr, and exit_code.
    """
    session = get_session(ctx, session_id)
    require_connected(session)

    env_script = _build_env_script(session)
    loop = asyncio.get_running_loop()

    def _exec() -> dict[str, Any]:
        if env_script:
            # Feed secrets via stdin so they never appear in /proc/*/cmdline
            script = env_script + f'exec bash -c {shlex.quote(command)}\n'
            stdin_ch, stdout_ch, stderr_ch = session.client.exec_command('bash', timeout=timeout)
            stdin_ch.write(script)
            stdin_ch.channel.shutdown_write()
        else:
            _, stdout_ch, stderr_ch = session.client.exec_command(command, timeout=timeout)
        stdout = stdout_ch.read().decode(errors='replace')
        stderr = stderr_ch.read().decode(errors='replace')
        exit_code = stdout_ch.channel.recv_exit_status()
        return {'stdout': stdout, 'stderr': stderr, 'exit_code': exit_code}

    result = await loop.run_in_executor(None, _exec)
    logger.debug(f'[{session_id}] exec exit={result["exit_code"]}: {command[:80]}')
    result['stdout'] = session.redact(result['stdout'])
    result['stderr'] = session.redact(result['stderr'])
    if session.transcript.enabled:
        session.transcript.record(
            'execute',
            command=command,
            stdout=result['stdout'],
            stderr=result['stderr'],
            exit_code=result['exit_code'],
        )
    return result


@mcp.tool()
async def ssh_sudo_execute(
    ctx: Context,
    session_id: str,
    command: str,
    sudo_password: str = '',
    timeout: int = 120,
) -> dict[str, Any]:
    """Execute a command with sudo on the remote host. If the user already
    has passwordless sudo, leave sudo_password empty.

    If secrets have been loaded via ssh_load_env_file, they are automatically
    injected as environment variables for this command.

    Args:
        session_id: The session ID returned by ssh_connect.
        command: Shell command to execute under sudo.
        sudo_password: Password for sudo prompt (empty for passwordless sudo).
        timeout: Maximum seconds to wait (default: 120).

    Returns:
        Dict with stdout, stderr, and exit_code.
    """
    session = get_session(ctx, session_id)
    require_connected(session)

    env_script = _build_env_script(session)

    if sudo_password:
        actual_cmd = f'echo {_shell_quote(sudo_password)} | sudo -SE {command}'
    else:
        actual_cmd = f'sudo -E {command}'

    loop = asyncio.get_running_loop()

    def _exec() -> dict[str, Any]:
        if env_script:
            script = env_script + f'exec bash -c {shlex.quote(actual_cmd)}\n'
            stdin_ch, stdout_ch, stderr_ch = session.client.exec_command('bash', timeout=timeout)
            stdin_ch.write(script)
            stdin_ch.channel.shutdown_write()
        else:
            _, stdout_ch, stderr_ch = session.client.exec_command(actual_cmd, timeout=timeout)
        stdout = stdout_ch.read().decode(errors='replace')
        stderr = stderr_ch.read().decode(errors='replace')
        exit_code = stdout_ch.channel.recv_exit_status()
        return {'stdout': stdout, 'stderr': stderr, 'exit_code': exit_code}

    result = await loop.run_in_executor(None, _exec)
    logger.debug(f'[{session_id}] sudo exec exit={result["exit_code"]}: {command[:80]}')
    result['stdout'] = session.redact(result['stdout'])
    result['stderr'] = session.redact(result['stderr'])
    if session.transcript.enabled:
        session.transcript.record(
            'execute',
            command=f'sudo {command}',
            stdout=result['stdout'],
            stderr=result['stderr'],
            exit_code=result['exit_code'],
        )
    return result


def _shell_quote(s: str) -> str:
    """Quote a string for safe use in shell (single-quote wrapping)."""
    return "'" + s.replace("'", "'\"'\"'") + "'"
