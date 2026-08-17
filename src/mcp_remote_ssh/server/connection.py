from __future__ import annotations

import asyncio
from typing import Any

import paramiko
from fastmcp import Context
from loguru import logger

from mcp_remote_ssh.server import mcp
from mcp_remote_ssh.server.helpers import get_session, get_store
from mcp_remote_ssh.session import SSHSession


@mcp.tool()
async def ssh_connect(
    ctx: Context,
    host: str,
    username: str = 'root',
    password: str = '',
    key_path: str = '',
    port: int = 22,
    timeout: int = 60,
    record: bool = False,
) -> dict[str, Any]:
    """Connect to a remote host via SSH. Returns a session_id for use with all
    other tools. Supports password and key-based authentication.

    Args:
        host: Hostname or IP address of the remote server.
        username: SSH username (default: root).
        password: Password for authentication. Leave empty for key-based auth.
        key_path: Path to SSH private key file. Leave empty for password auth.
        port: SSH port (default: 22).
        timeout: Connection timeout in seconds (default: 60).
        record: Start transcript recording immediately on connect (default: False).

    Returns:
        Session info dict with session_id, host, and connection status.
    """
    store = get_store(ctx)
    session = SSHSession(host=host, username=username, port=port)
    # AutoAddPolicy: accepts unknown host keys without prompting. Intentional for
    # QE/lab environments where hosts are ephemeral (Beaker, cloud instances, CI).
    # MITM risk is accepted on trusted internal networks. For strict environments,
    # a host_key_policy parameter could be added in the future.
    session.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # noqa: S507

    connect_kwargs: dict[str, Any] = {
        'hostname': host,
        'port': port,
        'username': username,
        'timeout': timeout,
        'allow_agent': False,
        'look_for_keys': False,
    }
    if key_path:
        connect_kwargs['key_filename'] = key_path
        connect_kwargs['look_for_keys'] = True
    elif password:
        connect_kwargs['password'] = password
    else:
        connect_kwargs['allow_agent'] = True
        connect_kwargs['look_for_keys'] = True

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, lambda: session.client.connect(**connect_kwargs))

    if record:
        session.transcript.enabled = True
        session.transcript.record('connect', host=host, username=username, port=port)

    await store.add(session)
    logger.info(f'Connected to {username}@{host}:{port} as session {session.session_id}')
    return session.summary()


@mcp.tool()
async def ssh_list_sessions(ctx: Context) -> list[dict[str, Any]]:
    """List all active SSH sessions with their connection status and details.

    Returns:
        List of session info dicts.
    """
    store = get_store(ctx)
    return store.list_all()


@mcp.tool()
async def ssh_close_session(ctx: Context, session_id: str) -> str:
    """Close an SSH session and release all its resources (shell, SFTP,
    port forwards). WARNING: this kills any running processes in the session.

    Args:
        session_id: The session ID returned by ssh_connect.

    Returns:
        Confirmation message.
    """
    store = get_store(ctx)
    session = get_session(ctx, session_id)
    if session.transcript.enabled:
        session.transcript.record('disconnect', host=session.host, entries=len(session.transcript.entries))
    errors = session.close()
    await store.remove(session_id)
    logger.info(f'Closed session {session_id} to {session.host}')
    if errors:
        return f'Session {session_id} closed with warnings: {"; ".join(errors)}'
    return f'Session {session_id} to {session.host} closed.'
