from __future__ import annotations

import json
from typing import Any

from fastmcp import Context

from mcp_remote_ssh.server import mcp
from mcp_remote_ssh.server.helpers import get_session


@mcp.tool()
async def ssh_start_recording(ctx: Context, session_id: str) -> str:
    """Start recording all SSH interactions (commands, output, shell I/O)
    for this session. If already recording, this is a no-op.

    Args:
        session_id: The session ID returned by ssh_connect.

    Returns:
        Confirmation message.
    """
    session = get_session(ctx, session_id)
    if session.transcript.enabled:
        return f'Session {session_id} is already recording ({len(session.transcript.entries)} entries so far).'
    session.transcript.enabled = True
    session.transcript.record('recording_started')
    return f'Recording started for session {session_id} to {session.host}.'


@mcp.tool()
async def ssh_stop_recording(ctx: Context, session_id: str) -> str:
    """Stop recording SSH interactions for this session. The transcript
    is preserved and can still be retrieved with ssh_get_transcript.

    Args:
        session_id: The session ID returned by ssh_connect.

    Returns:
        Confirmation with entry count.
    """
    session = get_session(ctx, session_id)
    if not session.transcript.enabled:
        return f'Session {session_id} is not recording.'
    session.transcript.record('recording_stopped')
    session.transcript.enabled = False
    return f'Recording stopped for session {session_id}. {len(session.transcript.entries)} entries captured.'


@mcp.tool()
async def ssh_get_transcript(
    ctx: Context,
    session_id: str,
    fmt: str = 'text',
    last_n: int = 0,
) -> dict[str, Any]:
    """Retrieve the session transcript. Can return all entries or just the
    last N. Supports text (human-readable) or jsonl format.

    Args:
        session_id: The session ID returned by ssh_connect.
        fmt: Output format -- "text" for human-readable log, "jsonl" for structured JSON lines (default: text).
        last_n: Return only the last N entries. 0 means all (default: 0).

    Returns:
        Dict with entry count and transcript content.
    """
    session = get_session(ctx, session_id)
    transcript = session.transcript
    entries = transcript.entries
    if last_n > 0:
        entries = entries[-last_n:]

    if fmt == 'jsonl':
        content = '\n'.join(json.dumps(e.to_dict()) for e in entries)
    else:
        content = '\n'.join(e.to_text() for e in entries)

    return {
        'session_id': session_id,
        'host': session.host,
        'total_entries': len(transcript.entries),
        'returned_entries': len(entries),
        'recording': transcript.enabled,
        'transcript': content,
    }


@mcp.tool()
async def ssh_save_transcript(
    ctx: Context,
    session_id: str,
    path: str,
    fmt: str = 'text',
) -> str:
    """Save the session transcript to a local file on the machine running
    the MCP server (not the remote host).

    Args:
        session_id: The session ID returned by ssh_connect.
        path: Local file path to save the transcript to.
        fmt: Format -- "text" for human-readable, "jsonl" for structured (default: text).

    Returns:
        Confirmation with file path and entry count.
    """
    session = get_session(ctx, session_id)
    count = session.transcript.save(path, fmt=fmt)
    return f'Transcript saved: {count} entries written to {path}'
