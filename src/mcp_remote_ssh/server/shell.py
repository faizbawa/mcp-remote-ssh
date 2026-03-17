from __future__ import annotations

import asyncio
import time

from fastmcp import Context
from loguru import logger

from mcp_remote_ssh.server import mcp
from mcp_remote_ssh.server.helpers import get_session, require_connected, require_shell


@mcp.tool()
async def ssh_shell_open(
    ctx: Context,
    session_id: str,
    term: str = 'xterm',
    width: int = 200,
    height: int = 50,
) -> str:
    """Open a persistent interactive shell on the SSH session. The shell
    preserves working directory, environment variables, and running processes
    across multiple send/read calls. Ideal for screen/tmux, long builds, etc.

    If a shell is already open, this is a no-op (returns existing shell info).

    Args:
        session_id: The session ID returned by ssh_connect.
        term: Terminal type (default: xterm).
        width: Terminal width in columns (default: 200).
        height: Terminal height in rows (default: 50).

    Returns:
        Confirmation that the shell is open.
    """
    session = get_session(ctx, session_id)
    require_connected(session)

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, lambda: session.shell_open(term=term, width=width, height=height))

    await asyncio.sleep(0.5)
    initial = await loop.run_in_executor(None, lambda: session.shell_read_buffer(lines=20))
    logger.info(f'[{session_id}] Interactive shell opened')
    return f'Shell opened on {session.host}.\n\n{initial}'


@mcp.tool()
async def ssh_shell_send(
    ctx: Context,
    session_id: str,
    data: str,
    press_enter: bool = True,
    wait: float = 1.0,
    read_lines: int = 100,
) -> str:
    """Send text to the interactive shell. By default appends Enter (newline)
    and waits briefly to capture output.

    Args:
        session_id: The session ID returned by ssh_connect.
        data: Text to send to the shell.
        press_enter: Whether to append a newline after the text (default: True).
        wait: Seconds to wait for output after sending (default: 1.0).
        read_lines: Number of tail lines to return from the shell buffer (default: 100).

    Returns:
        Recent shell output (tail of buffer).
    """
    session = get_session(ctx, session_id)
    require_shell(session)

    payload = data + '\n' if press_enter else data
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, lambda: session.shell_send(payload))

    if wait > 0:
        await asyncio.sleep(wait)

    output = await loop.run_in_executor(None, lambda: session.shell_read_buffer(lines=read_lines))
    return output


@mcp.tool()
async def ssh_shell_read(
    ctx: Context,
    session_id: str,
    lines: int = 100,
) -> str:
    """Read the current content of the interactive shell buffer. Use this to
    poll for output from long-running commands without sending anything.

    Args:
        session_id: The session ID returned by ssh_connect.
        lines: Number of tail lines to return (default: 100).

    Returns:
        Recent shell output (tail of buffer).
    """
    session = get_session(ctx, session_id)
    require_shell(session)

    loop = asyncio.get_running_loop()
    output = await loop.run_in_executor(None, lambda: session.shell_read_buffer(lines=lines))
    return output


@mcp.tool()
async def ssh_shell_send_control(
    ctx: Context,
    session_id: str,
    key: str,
) -> str:
    """Send a control character to the interactive shell. Common keys:
    "c" for Ctrl+C (interrupt), "d" for Ctrl+D (EOF), "z" for Ctrl+Z (suspend),
    "l" for Ctrl+L (clear screen), "a" for Ctrl+A (screen prefix).

    Args:
        session_id: The session ID returned by ssh_connect.
        key: Single letter for the control key (e.g. "c" sends Ctrl+C).

    Returns:
        Confirmation and recent shell output.
    """
    session = get_session(ctx, session_id)
    require_shell(session)

    if len(key) != 1 or not key.isalpha():
        msg = f'key must be a single letter (a-z), got: {key!r}'
        raise ValueError(msg)

    ctrl_char = chr(ord(key.lower()) - ord('a') + 1)
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, lambda: session.shell_send(ctrl_char))

    await asyncio.sleep(0.5)
    output = await loop.run_in_executor(None, lambda: session.shell_read_buffer(lines=30))
    return f'Sent Ctrl+{key.upper()}\n\n{output}'


@mcp.tool()
async def ssh_shell_wait(
    ctx: Context,
    session_id: str,
    pattern: str = '',
    timeout: int = 300,
    poll_interval: float = 2.0,
    lines: int = 100,
) -> str:
    """Wait for the shell output to contain a specific pattern, or for the
    output to stabilize (no new output for two poll intervals). Useful for
    waiting on long-running commands to complete.

    Args:
        session_id: The session ID returned by ssh_connect.
        pattern: Text pattern to wait for (e.g. a shell prompt like "$ " or "# "). If empty, waits for output to stabilize.
        timeout: Maximum seconds to wait (default: 300).
        poll_interval: Seconds between polls (default: 2.0).
        lines: Number of tail lines to return (default: 100).

    Returns:
        Shell output when the pattern is found or output stabilizes.
    """
    session = get_session(ctx, session_id)
    require_shell(session)

    loop = asyncio.get_running_loop()
    start = time.monotonic()
    prev_output = ''
    stable_count = 0

    while (time.monotonic() - start) < timeout:
        await asyncio.sleep(poll_interval)
        output = await loop.run_in_executor(None, lambda: session.shell_read_buffer(lines=lines))

        if pattern and pattern in output:
            return output

        if not pattern:
            if output == prev_output:
                stable_count += 1
                if stable_count >= 2:
                    return output
            else:
                stable_count = 0
            prev_output = output

    elapsed = int(time.monotonic() - start)
    output = await loop.run_in_executor(None, lambda: session.shell_read_buffer(lines=lines))
    if pattern:
        return f'Timeout after {elapsed}s waiting for pattern "{pattern}". Latest output:\n\n{output}'
    return f'Timeout after {elapsed}s (output may still be changing). Latest output:\n\n{output}'
