from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, AsyncIterator

from loguru import logger

from mcp_remote_ssh.session import SessionStore

if TYPE_CHECKING:
    from fastmcp import FastMCP


@dataclass
class LifespanContext:
    sessions: SessionStore


@asynccontextmanager
async def lifespan(app: FastMCP) -> AsyncIterator[LifespanContext]:
    ctx = LifespanContext(sessions=SessionStore())
    try:
        yield ctx
    finally:
        for info in ctx.sessions.list_all():
            sid = info['session_id']
            session = ctx.sessions.get(sid)
            errors = session.close()
            if errors:
                logger.warning(f'Session {sid} cleanup errors: {errors}')
            else:
                logger.debug(f'Cleaned up session {sid}')
