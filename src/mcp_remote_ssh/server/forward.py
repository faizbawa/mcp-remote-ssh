from __future__ import annotations

import asyncio
import select
import socket
import threading
import uuid
from typing import Any

from fastmcp import Context
from loguru import logger

from mcp_remote_ssh.server import mcp
from mcp_remote_ssh.server.helpers import get_session, require_connected
from mcp_remote_ssh.session import PortForward


def _forward_tunnel(
    local_port: int,
    remote_host: str,
    remote_port: int,
    transport,
    stop_event: threading.Event,
    fwd: PortForward,
) -> None:
    """Run a local port forward in a background thread."""
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(('127.0.0.1', local_port))
    server_sock.listen(5)
    server_sock.settimeout(1.0)
    fwd._server_socket = server_sock

    logger.info(f'Port forward listening on 127.0.0.1:{local_port} -> {remote_host}:{remote_port}')

    while not stop_event.is_set():
        try:
            client_sock, addr = server_sock.accept()
        except socket.timeout:
            continue
        except OSError:
            break

        try:
            channel = transport.open_channel(
                'direct-tcpip',
                (remote_host, remote_port),
                client_sock.getpeername(),
            )
        except Exception as e:  # noqa: BLE001
            logger.warning(f'Port forward channel open failed: {e}')
            client_sock.close()
            continue

        if channel is None:
            client_sock.close()
            continue

        t = threading.Thread(
            target=_proxy_data,
            args=(client_sock, channel, stop_event),
            daemon=True,
        )
        t.start()

    server_sock.close()


def _proxy_data(sock: socket.socket, channel, stop_event: threading.Event) -> None:
    """Bidirectionally proxy data between a local socket and an SSH channel."""
    try:
        while not stop_event.is_set():
            r, _, _ = select.select([sock, channel], [], [], 1.0)
            if sock in r:
                data = sock.recv(65536)
                if not data:
                    break
                channel.sendall(data)
            if channel in r:
                data = channel.recv(65536)
                if not data:
                    break
                sock.sendall(data)
    except Exception:  # noqa: BLE001
        pass
    finally:
        sock.close()
        channel.close()


@mcp.tool()
async def ssh_forward_port(
    ctx: Context,
    session_id: str,
    remote_port: int,
    local_port: int = 0,
    remote_host: str = 'localhost',
) -> dict[str, Any]:
    """Create an SSH port forward (local -> remote). Connections to
    127.0.0.1:local_port will be tunneled through SSH to remote_host:remote_port.

    If local_port is 0, a random available port is chosen.

    Args:
        session_id: The session ID returned by ssh_connect.
        remote_port: Port on the remote side to forward to.
        local_port: Local port to listen on (0 = auto-assign).
        remote_host: Host on the remote side (default: localhost, i.e. the SSH server itself).

    Returns:
        Dict with forward_id, local_port, remote_host, and remote_port.
    """
    session = get_session(ctx, session_id)
    require_connected(session)

    transport = session.client.get_transport()

    if local_port == 0:
        tmp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tmp_sock.bind(('127.0.0.1', 0))
        local_port = tmp_sock.getsockname()[1]
        tmp_sock.close()

    fwd = PortForward(
        forward_id=uuid.uuid4().hex[:8],
        local_port=local_port,
        remote_host=remote_host,
        remote_port=remote_port,
    )

    t = threading.Thread(
        target=_forward_tunnel,
        args=(local_port, remote_host, remote_port, transport, fwd._stop_event, fwd),
        daemon=True,
    )
    fwd._thread = t
    t.start()

    session._forwards[fwd.forward_id] = fwd
    logger.info(f'[{session_id}] Port forward {fwd.forward_id}: 127.0.0.1:{local_port} -> {remote_host}:{remote_port}')
    return fwd.summary()


@mcp.tool()
async def ssh_list_forwards(ctx: Context, session_id: str) -> list[dict[str, Any]]:
    """List all active port forwards for an SSH session.

    Args:
        session_id: The session ID returned by ssh_connect.

    Returns:
        List of forward info dicts.
    """
    session = get_session(ctx, session_id)
    return [f.summary() for f in session._forwards.values()]


@mcp.tool()
async def ssh_close_forward(ctx: Context, session_id: str, forward_id: str) -> str:
    """Close a specific port forward.

    Args:
        session_id: The session ID returned by ssh_connect.
        forward_id: The forward ID returned by ssh_forward_port.

    Returns:
        Confirmation message.
    """
    session = get_session(ctx, session_id)
    fwd = session._forwards.pop(forward_id, None)
    if fwd is None:
        active = ', '.join(session._forwards.keys()) or 'none'
        msg = f'Forward not found: {forward_id}. Active forwards: {active}'
        raise ValueError(msg)

    fwd._stop_event.set()
    if fwd._server_socket:
        fwd._server_socket.close()
    if fwd._thread and fwd._thread.is_alive():
        fwd._thread.join(timeout=2)

    logger.info(f'[{session_id}] Closed forward {forward_id} (127.0.0.1:{fwd.local_port})')
    return f'Closed forward {forward_id} (127.0.0.1:{fwd.local_port} -> {fwd.remote_host}:{fwd.remote_port})'
