# mcp-remote-ssh

MCP server for remote SSH operations. Gives AI agents persistent SSH sessions, structured command output, SFTP file transfer, and SSH port forwarding -- with native password and key-based authentication.

## Why this exists

Existing SSH MCP servers each solve part of the problem but none combine all of:

- **Password + key auth** -- connect to any host, whether it uses passwords, SSH keys, or an agent
- **Dual execution model** -- one-shot `exec_command()` with real exit codes *and* persistent interactive shells for long-running workflows
- **SFTP** -- read, write, upload, download files properly instead of piping through a PTY
- **Port forwarding** -- SSH tunnels for accessing remote services (databases, web UIs, VNC, etc.)
- **Structured output** -- `stdout`, `stderr`, and `exit_code` as separate fields, not screen scrapes

## Installation

```bash
# Via uv (recommended)
uv tool install mcp-remote-ssh

# Via pip
pip install mcp-remote-ssh

# From source
git clone https://github.com/faizbawa/mcp-remote-ssh.git
cd mcp-remote-ssh
uv sync
```

## Configuration

### Cursor / Claude Desktop

Add to your MCP client configuration:

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

Or if running from source:

```json
{
  "mcpServers": {
    "remote-ssh": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/mcp-remote-ssh", "mcp-remote-ssh"]
    }
  }
}
```

## Tools (18 total)

### Connection management

| Tool | Description |
|---|---|
| `ssh_connect` | Connect to a host (password, key, or agent auth). Returns `session_id`. |
| `ssh_list_sessions` | List all active sessions with status |
| `ssh_close_session` | Close a session and release all resources |

### Structured execution (one-shot, clean output)

| Tool | Description |
|---|---|
| `ssh_execute` | Run a command, returns `{stdout, stderr, exit_code}` |
| `ssh_sudo_execute` | Run a command with sudo elevation |

### Interactive shell (persistent state)

| Tool | Description |
|---|---|
| `ssh_shell_open` | Open a persistent interactive shell (`invoke_shell`) |
| `ssh_shell_send` | Send text to the shell (with optional Enter) |
| `ssh_shell_read` | Read current shell buffer (poll for output) |
| `ssh_shell_send_control` | Send Ctrl+C, Ctrl+D, etc. |
| `ssh_shell_wait` | Wait for a pattern or output to stabilize |

### File transfer (SFTP)

| Tool | Description |
|---|---|
| `ssh_upload_file` | Upload a local file to the remote host |
| `ssh_download_file` | Download a remote file to local machine |
| `ssh_read_remote_file` | Read a text file on the remote host |
| `ssh_write_remote_file` | Write text to a remote file (create or append) |
| `ssh_list_remote_dir` | List directory contents with metadata |

### Port forwarding

| Tool | Description |
|---|---|
| `ssh_forward_port` | Create an SSH tunnel (local port -> remote port) |
| `ssh_list_forwards` | List active port forwards for a session |
| `ssh_close_forward` | Close a specific port forward |

## Quick start

```text
# Connect with password
ssh_connect(host="myserver.example.com", username="admin", password="secret")
→ {"session_id": "a1b2c3d4", "connected": true, ...}

# Run a structured command
ssh_execute(session_id="a1b2c3d4", command="df -h /")
→ {"stdout": "Filesystem  Size  Used ...", "stderr": "", "exit_code": 0}

# Open a persistent shell for interactive work
ssh_shell_open(session_id="a1b2c3d4")
ssh_shell_send(session_id="a1b2c3d4", data="cd /opt && make -j$(nproc)")
ssh_shell_wait(session_id="a1b2c3d4", pattern="$ ", timeout=600)

# Transfer files via SFTP
ssh_upload_file(session_id="a1b2c3d4", local_path="config.yaml", remote_path="/etc/app/config.yaml")
ssh_read_remote_file(session_id="a1b2c3d4", remote_path="/var/log/app.log")

# Set up an SSH tunnel
ssh_forward_port(session_id="a1b2c3d4", remote_port=5432, local_port=15432)
# Now connect to localhost:15432 to reach the remote PostgreSQL
```

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
|---|---|
| [FastMCP](https://github.com/PrefectHQ/fastmcp) | MCP protocol handling |
| [Paramiko](https://www.paramiko.org/) | SSH2 protocol (connections, channels, SFTP) |
| [Click](https://click.palletsprojects.com/) | CLI interface |
| [Loguru](https://loguru.readthedocs.io/) | Logging |

## License

MIT
