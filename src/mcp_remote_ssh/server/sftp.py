from __future__ import annotations

import asyncio
import stat
from typing import Any

from fastmcp import Context
from loguru import logger

from mcp_remote_ssh.server import mcp
from mcp_remote_ssh.server.helpers import get_session, require_connected


@mcp.tool()
async def ssh_upload_file(
    ctx: Context,
    session_id: str,
    local_path: str,
    remote_path: str,
) -> str:
    """Upload a local file to the remote host via SFTP.

    Args:
        session_id: The session ID returned by ssh_connect.
        local_path: Path to the file on the local machine.
        remote_path: Destination path on the remote host.

    Returns:
        Confirmation message with file size.
    """
    session = get_session(ctx, session_id)
    require_connected(session)

    loop = asyncio.get_running_loop()

    def _upload() -> int:
        session.sftp.put(local_path, remote_path)
        info = session.sftp.stat(remote_path)
        return info.st_size

    size = await loop.run_in_executor(None, _upload)
    logger.info(f'[{session_id}] Uploaded {local_path} -> {remote_path} ({size} bytes)')
    return f'Uploaded {local_path} to {session.host}:{remote_path} ({size} bytes)'


@mcp.tool()
async def ssh_download_file(
    ctx: Context,
    session_id: str,
    remote_path: str,
    local_path: str,
) -> str:
    """Download a file from the remote host to the local machine via SFTP.

    Args:
        session_id: The session ID returned by ssh_connect.
        remote_path: Path to the file on the remote host.
        local_path: Destination path on the local machine.

    Returns:
        Confirmation message with file size.
    """
    session = get_session(ctx, session_id)
    require_connected(session)

    loop = asyncio.get_running_loop()

    def _download() -> int:
        info = session.sftp.stat(remote_path)
        session.sftp.get(remote_path, local_path)
        return info.st_size

    size = await loop.run_in_executor(None, _download)
    logger.info(f'[{session_id}] Downloaded {remote_path} -> {local_path} ({size} bytes)')
    return f'Downloaded {session.host}:{remote_path} to {local_path} ({size} bytes)'


@mcp.tool()
async def ssh_read_remote_file(
    ctx: Context,
    session_id: str,
    remote_path: str,
    max_bytes: int = 1_000_000,
) -> str:
    """Read a text file on the remote host and return its contents. For large
    files, use max_bytes to limit the amount read.

    Args:
        session_id: The session ID returned by ssh_connect.
        remote_path: Path to the file on the remote host.
        max_bytes: Maximum bytes to read (default: 1MB). Set to 0 for no limit.

    Returns:
        File contents as text.
    """
    session = get_session(ctx, session_id)
    require_connected(session)

    loop = asyncio.get_running_loop()

    def _read() -> str:
        with session.sftp.open(remote_path, 'r') as f:
            if max_bytes > 0:
                data = f.read(max_bytes)
            else:
                data = f.read()
        if isinstance(data, bytes):
            return data.decode(errors='replace')
        return data

    content = await loop.run_in_executor(None, _read)
    return content


@mcp.tool()
async def ssh_write_remote_file(
    ctx: Context,
    session_id: str,
    remote_path: str,
    content: str,
    append: bool = False,
) -> str:
    """Write text content to a file on the remote host via SFTP.

    Args:
        session_id: The session ID returned by ssh_connect.
        remote_path: Path to the file on the remote host.
        content: Text content to write.
        append: If True, append to existing file instead of overwriting (default: False).

    Returns:
        Confirmation message with bytes written.
    """
    session = get_session(ctx, session_id)
    require_connected(session)

    loop = asyncio.get_running_loop()
    mode = 'a' if append else 'w'

    def _write() -> int:
        with session.sftp.open(remote_path, mode) as f:
            f.write(content)
        return len(content.encode())

    size = await loop.run_in_executor(None, _write)
    action = 'Appended to' if append else 'Wrote'
    logger.info(f'[{session_id}] {action} {remote_path} ({size} bytes)')
    return f'{action} {session.host}:{remote_path} ({size} bytes)'


@mcp.tool()
async def ssh_list_remote_dir(
    ctx: Context,
    session_id: str,
    remote_path: str = '.',
) -> list[dict[str, Any]]:
    """List files and directories at a path on the remote host via SFTP.

    Args:
        session_id: The session ID returned by ssh_connect.
        remote_path: Directory path on the remote host (default: current directory).

    Returns:
        List of dicts with name, size, modified timestamp, and is_dir flag.
    """
    session = get_session(ctx, session_id)
    require_connected(session)

    loop = asyncio.get_running_loop()

    def _listdir() -> list[dict[str, Any]]:
        entries = session.sftp.listdir_attr(remote_path)
        result = []
        for entry in entries:
            result.append({
                'name': entry.filename,
                'size': entry.st_size,
                'modified': entry.st_mtime,
                'is_dir': stat.S_ISDIR(entry.st_mode) if entry.st_mode else False,
            })
        result.sort(key=lambda e: (not e['is_dir'], e['name']))
        return result

    return await loop.run_in_executor(None, _listdir)
