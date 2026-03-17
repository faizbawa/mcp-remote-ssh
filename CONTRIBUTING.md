# Contributing to mcp-remote-ssh

Thanks for your interest in contributing! This document covers the setup, workflow, and guidelines for the project.

## Development setup

```bash
git clone https://github.com/faizbawa/mcp-remote-ssh.git
cd mcp-remote-ssh
uv sync --group dev
```

This installs the package in editable mode along with test and lint dependencies.

## Running the server locally

```bash
# stdio (default)
uv run mcp-remote-ssh

# SSE (for browser-based MCP clients)
uv run mcp-remote-ssh --transport sse --port 9810
```

## Code quality

We use [Ruff](https://docs.astral.sh/ruff/) for linting and formatting:

```bash
# Lint
uv run ruff check src/

# Auto-fix lint issues
uv run ruff check src/ --fix

# Format
uv run ruff format src/
```

All code should pass `ruff check` with the rules defined in `pyproject.toml` before submitting a PR.

## Running tests

```bash
uv run pytest tests/ -v
```

If your change adds a new tool or modifies existing behavior, please add or update tests.

## Project structure

```
src/mcp_remote_ssh/
├── __init__.py          # CLI entry point
├── lifespan.py          # FastMCP lifespan (session cleanup on shutdown)
├── session.py           # SSHSession, SessionStore, PortForward
└── server/
    ├── __init__.py      # FastMCP app instance + tool imports
    ├── helpers.py       # Shared helpers (get_session, require_connected, etc.)
    ├── connection.py    # ssh_connect, ssh_list_sessions, ssh_close_session
    ├── execute.py       # ssh_execute, ssh_sudo_execute
    ├── shell.py         # ssh_shell_open, ssh_shell_send, ssh_shell_read, ...
    ├── sftp.py          # ssh_upload_file, ssh_download_file, ssh_read_remote_file, ...
    └── forward.py       # ssh_forward_port, ssh_list_forwards, ssh_close_forward
```

**Key conventions:**

- Each tool module imports `mcp` from `server/__init__.py` and registers tools with `@mcp.tool()`
- All Paramiko (blocking) calls are wrapped in `asyncio.get_running_loop().run_in_executor(None, ...)`
- Session state lives in `SSHSession` dataclass; the `SessionStore` is async-lock-protected
- Tool functions get the session via `get_session(ctx, session_id)` from `helpers.py`

## Adding a new tool

1. Pick the appropriate module (or create a new one under `server/`)
2. Write the tool function with `@mcp.tool()` decorator
3. Use clear docstrings -- the `Args:` and `Returns:` sections become the tool description visible to AI agents
4. If your module is new, import it in `server/__init__.py`
5. Add tests and verify with `uv run pytest`

## Submitting changes

1. Fork the repo and create a feature branch from `main`
2. Make your changes with clear, focused commits
3. Ensure `ruff check` and `pytest` pass
4. Open a pull request against `main` with a description of what and why

## Reporting issues

Open an issue at https://github.com/faizbawa/mcp-remote-ssh/issues with:

- What you expected to happen
- What actually happened
- Steps to reproduce (MCP client, Python version, OS, SSH server type)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
