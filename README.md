# mcp-remote-ssh

[![PyPI version](https://img.shields.io/pypi/v/mcp-remote-ssh.svg)](https://pypi.org/project/mcp-remote-ssh/)
[![Python](https://img.shields.io/pypi/pyversions/mcp-remote-ssh.svg)](https://pypi.org/project/mcp-remote-ssh/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

MCP server for remote SSH operations. Gives AI agents persistent SSH sessions, structured command output, SFTP file transfer, and SSH port forwarding -- with native password and key-based authentication.

Works with any SSH server -- Linux, macOS, Windows (OpenSSH), network devices -- on any architecture.

## Features

- **Password + key + agent auth** -- connect to any host, whether it uses passwords, SSH keys, or an agent
- **Structured execution** -- one-shot commands returning `{stdout, stderr, exit_code}` as separate fields
- **Interactive shell** -- persistent `invoke_shell` sessions that preserve working directory, env vars, and running processes across calls
- **SFTP file transfer** -- upload, download, read, write, and list remote files and directories
- **Port forwarding** -- SSH tunnels for accessing remote services (databases, web UIs, VNC, etc.)
- **Multi-session** -- connect to multiple hosts simultaneously
- **Pure Python** -- runs on any platform, install via `uvx` or `pip`

## Installation

```bash
# Using uvx (recommended)
uvx mcp-remote-ssh

# Using pip
pip install mcp-remote-ssh
```

**PyPI**: https://pypi.org/project/mcp-remote-ssh/

## Configuration

Add to your MCP client config (Cursor, Claude Desktop, etc.):

```json
{
  "mcpServers": {
    "remote-ssh": {
      "command": "uvx",
      "args": ["mcp-remote-ssh"]
    }
  }
}
```

No environment variables needed -- all connection details are passed per-call via `ssh_connect`.

## Usage

### Connect with password

```
ssh_connect(host="myserver.example.com", username="admin", password="secret")
→ {"session_id": "a1b2c3d4", "connected": true, ...}
```

### Connect with SSH key

```
ssh_connect(host="myserver.example.com", username="deploy", key_path="~/.ssh/id_ed25519")
```

### Connect with SSH agent (default key discovery)

```
ssh_connect(host="myserver.example.com", username="deploy")
```

### Run structured commands

```
ssh_execute(session_id="a1b2c3d4", command="df -h /")
→ {"stdout": "Filesystem  Size  Used ...", "stderr": "", "exit_code": 0}

ssh_execute(session_id="a1b2c3d4", command="cat /nonexistent")
→ {"stdout": "", "stderr": "cat: /nonexistent: No such file or directory", "exit_code": 1}
```

### Interactive shell (persistent state)

```
ssh_shell_open(session_id="a1b2c3d4")
ssh_shell_send(session_id="a1b2c3d4", data="cd /opt && make -j$(nproc)")
ssh_shell_wait(session_id="a1b2c3d4", pattern="$ ", timeout=600)

# Send Ctrl+C to interrupt
ssh_shell_send_control(session_id="a1b2c3d4", key="c")
```

### File transfer (SFTP)

```
ssh_upload_file(session_id="a1b2c3d4", local_path="config.yaml", remote_path="/etc/app/config.yaml")
ssh_download_file(session_id="a1b2c3d4", remote_path="/var/log/app.log", local_path="./app.log")
ssh_read_remote_file(session_id="a1b2c3d4", remote_path="/etc/hostname")
ssh_write_remote_file(session_id="a1b2c3d4", remote_path="/tmp/note.txt", content="hello world")
ssh_list_remote_dir(session_id="a1b2c3d4", remote_path="/var/log")
```

### Port forwarding

```
ssh_forward_port(session_id="a1b2c3d4", remote_port=5432, local_port=15432)
# Now connect to localhost:15432 to reach the remote PostgreSQL

ssh_list_forwards(session_id="a1b2c3d4")
ssh_close_forward(session_id="a1b2c3d4", forward_id="fwd123")
```

## Available Tools (18 tools)

### Connection Management

| Tool | Description |
|------|-------------|
| `ssh_connect` | Connect to a host (password, key, or agent auth). Returns `session_id`. |
| `ssh_list_sessions` | List all active sessions with status |
| `ssh_close_session` | Close a session and release all resources |

### Structured Execution

| Tool | Description |
|------|-------------|
| `ssh_execute` | Run a command, returns `{stdout, stderr, exit_code}` |
| `ssh_sudo_execute` | Run a command with sudo elevation |

### Interactive Shell

| Tool | Description |
|------|-------------|
| `ssh_shell_open` | Open a persistent interactive shell (`invoke_shell`) |
| `ssh_shell_send` | Send text to the shell (with optional Enter) |
| `ssh_shell_read` | Read current shell buffer (poll for output) |
| `ssh_shell_send_control` | Send Ctrl+C, Ctrl+D, etc. |
| `ssh_shell_wait` | Wait for a pattern or output to stabilize |

### File Transfer (SFTP)

| Tool | Description |
|------|-------------|
| `ssh_upload_file` | Upload a local file to the remote host |
| `ssh_download_file` | Download a remote file to local machine |
| `ssh_read_remote_file` | Read a text file on the remote host |
| `ssh_write_remote_file` | Write text to a remote file (create or append) |
| `ssh_list_remote_dir` | List directory contents with metadata |

### Port Forwarding

| Tool | Description |
|------|-------------|
| `ssh_forward_port` | Create an SSH tunnel (local port -> remote port) |
| `ssh_list_forwards` | List active port forwards for a session |
| `ssh_close_forward` | Close a specific port forward |

## Architecture

```
src/mcp_remote_ssh/
├── __init__.py          # CLI entry point (click)
├── lifespan.py          # FastMCP lifespan (session cleanup)
├── session.py           # SSHSession, SessionStore, PortForward
└── server/
    ├── __init__.py      # FastMCP app + tool registration
    ├── helpers.py       # get_session, require_connected, require_shell
    ├── connection.py    # ssh_connect, ssh_list_sessions, ssh_close_session
    ├── execute.py       # ssh_execute, ssh_sudo_execute
    ├── shell.py         # ssh_shell_open/send/read/control/wait
    ├── sftp.py          # upload, download, read, write, list_dir
    └── forward.py       # forward_port, list_forwards, close_forward
```

### Key design decisions

- **[Paramiko](https://www.paramiko.org/)** for SSH -- mature, pure-Python, supports password auth, SFTP, channels, and port forwarding natively
- **[FastMCP](https://github.com/PrefectHQ/fastmcp)** for MCP protocol
- **Dual execution model** -- `exec_command()` for structured one-shot commands (returns exit codes), `invoke_shell()` for persistent interactive sessions
- **Async wrappers** -- all blocking Paramiko calls run in `run_in_executor` to avoid blocking the event loop
- **Shell buffer management** -- interactive shell keeps a 500KB rolling buffer for `shell_read` polling

## Transport options

```bash
# stdio (default, for Cursor/Claude Desktop)
mcp-remote-ssh

# SSE
mcp-remote-ssh --transport sse --host 0.0.0.0 --port 9810

# Streamable HTTP
mcp-remote-ssh --transport streamable-http --host 0.0.0.0 --port 9810
```

## Dependencies

| Package | Purpose |
|---------|---------|
| [FastMCP](https://github.com/PrefectHQ/fastmcp) | MCP protocol handling |
| [Paramiko](https://www.paramiko.org/) | SSH2 protocol (connections, channels, SFTP) |
| [Click](https://click.palletsprojects.com/) | CLI interface |
| [Loguru](https://loguru.readthedocs.io/) | Logging |

## Development

```bash
git clone https://github.com/faizbawa/mcp-remote-ssh.git
cd mcp-remote-ssh
uv sync --group dev          # install all deps including test tools
uv run pytest tests/ -v      # run the test suite
uv run ruff check src/       # lint
```

## License

MIT
