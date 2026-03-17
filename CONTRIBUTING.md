# Contributing

## Setup

```bash
git clone https://github.com/faizbawa/mcp-remote-ssh.git
cd mcp-remote-ssh
uv sync --group dev
```

## Code quality

```bash
uv run ruff check src/       # lint
uv run ruff format src/       # format
uv run pytest tests/ -v       # test
```

All code must pass `ruff check` before merging.

## Adding a tool

1. Add your function with `@mcp.tool()` in the appropriate `server/*.py` module
2. Wrap blocking Paramiko calls in `loop.run_in_executor(None, ...)`
3. Write clear docstrings -- `Args:` and `Returns:` sections become the tool description for AI agents
4. If it's a new module, import it in `server/__init__.py`

## Submitting changes

1. Fork and branch from `main`
2. Make focused commits
3. Ensure lint + tests pass
4. Open a PR with a short description of what and why

## Issues

File at https://github.com/faizbawa/mcp-remote-ssh/issues with repro steps.

## License

Contributions are licensed under MIT.
