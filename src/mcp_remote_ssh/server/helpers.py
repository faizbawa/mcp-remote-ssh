from __future__ import annotations

from typing import Any

from mcp_remote_ssh.session import SSHSession


def get_session(ctx: Any, session_id: str) -> SSHSession:
    """Retrieve an SSH session from the lifespan context."""
    return ctx.request_context.lifespan_context.sessions.get(session_id)


def get_store(ctx: Any):
    """Retrieve the SessionStore from the lifespan context."""
    return ctx.request_context.lifespan_context.sessions


def require_connected(session: SSHSession) -> None:
    """Raise if the SSH session is no longer connected."""
    if not session.is_connected:
        msg = (
            f'SSH session {session.session_id} to {session.host} is disconnected. '
            'Use ssh_connect to establish a new connection.'
        )
        raise RuntimeError(msg)


def require_shell(session: SSHSession) -> None:
    """Raise if the session has no interactive shell open."""
    if not session.has_shell:
        msg = (
            f'No interactive shell on session {session.session_id}. '
            'Use ssh_shell_open to start one.'
        )
        raise RuntimeError(msg)
