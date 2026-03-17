from fastmcp import FastMCP

from mcp_remote_ssh.lifespan import LifespanContext, lifespan

__all__ = ['mcp']

mcp = FastMCP('mcp-remote-ssh', lifespan=lifespan)

from mcp_remote_ssh.server import connection, execute, forward, sftp, shell  # noqa: E402, F401
