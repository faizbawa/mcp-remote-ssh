import asyncio
import sys
from pathlib import Path

import click
from loguru import logger

try:
    LOG_DIR = Path.home() / '.mcp_remote_ssh'
    LOG_DIR.mkdir(exist_ok=True)
    logger.add(LOG_DIR / 'log.log', rotation='10 MB')
except Exception as e:  # noqa: BLE001
    logger.error(f'Failed to set up logger directory: {e}')

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@click.command()
@click.option('--transport', type=click.Choice(['stdio', 'sse', 'streamable-http']), default='stdio')
@click.option('--host', default='0.0.0.0', help='Host to bind to for SSE or Streamable HTTP transport')  # noqa: S104
@click.option('--port', default=9810, help='Port to listen on for SSE or Streamable HTTP transport')
def main(
    transport: str,
    host: str,
    port: int,
) -> None:
    from mcp_remote_ssh.server import mcp

    if transport == 'stdio':
        asyncio.run(mcp.run_async(transport=transport))
    elif transport in ('sse', 'streamable-http'):
        asyncio.run(mcp.run_async(transport=transport, host=host, port=port))


if __name__ == '__main__':
    main()
