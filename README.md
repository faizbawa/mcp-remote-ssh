# mcp-remote-ssh

[![PyPI](https://img.shields.io/pypi/v/mcp-remote-ssh.svg)](https://pypi.org/project/mcp-remote-ssh/)
[![Python](https://img.shields.io/pypi/pyversions/mcp-remote-ssh.svg)](https://pypi.org/project/mcp-remote-ssh/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

MCP server giving AI agents full SSH access -- persistent sessions, structured command output, SFTP file transfer, and port forwarding. Works with any SSH server on any platform.

## Why this exists

Every other SSH MCP server is missing something: no password auth, no persistent sessions, no SFTP, no port forwarding, or no structured exit codes. This one has all of them.

## Installation

```bash
uvx mcp-remote-ssh        # or: pip install mcp-remote-ssh
```

## Configuration

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

## Tools (18)

### Connection

| Tool | Description |
|------|-------------|
| `ssh_connect` | Connect with password, key, or agent auth. Returns `session_id` |
| `ssh_list_sessions` | List active sessions |
| `ssh_close_session` | Close a session and release resources |

### Execution

| Tool | Description |
|------|-------------|
| `ssh_execute` | Run a command, returns `{stdout, stderr, exit_code}` |
| `ssh_sudo_execute` | Run with sudo elevation |

### Interactive Shell

| Tool | Description |
|------|-------------|
| `ssh_shell_open` | Open persistent shell (preserves cwd, env, processes) |
| `ssh_shell_send` | Send text (with optional Enter) |
| `ssh_shell_read` | Read current output buffer |
| `ssh_shell_send_control` | Send Ctrl+C, Ctrl+D, etc. |
| `ssh_shell_wait` | Wait for a pattern or output to stabilize |

### SFTP

| Tool | Description |
|------|-------------|
| `ssh_upload_file` | Upload local file to remote host |
| `ssh_download_file` | Download remote file to local machine |
| `ssh_read_remote_file` | Read a remote text file |
| `ssh_write_remote_file` | Write/append to a remote file |
| `ssh_list_remote_dir` | List directory with metadata |

### Port Forwarding

| Tool | Description |
|------|-------------|
| `ssh_forward_port` | Create SSH tunnel (local -> remote) |
| `ssh_list_forwards` | List active tunnels |
| `ssh_close_forward` | Close a tunnel |

## Quick start

```text
ssh_connect(host="server.example.com", username="admin", password="secret")
→ {"session_id": "a1b2c3d4", "connected": true}

ssh_execute(session_id="a1b2c3d4", command="uname -a")
→ {"stdout": "Linux ...", "stderr": "", "exit_code": 0}

ssh_shell_open(session_id="a1b2c3d4")
ssh_shell_send(session_id="a1b2c3d4", data="cd /opt && make -j$(nproc)")
ssh_shell_wait(session_id="a1b2c3d4", pattern="$ ", timeout=600)

ssh_upload_file(session_id="a1b2c3d4", local_path="config.yaml", remote_path="/etc/app/config.yaml")
ssh_forward_port(session_id="a1b2c3d4", remote_port=5432, local_port=15432)
```

## Design

Built on **[Paramiko](https://www.paramiko.org/)** (SSH) + **[FastMCP](https://github.com/PrefectHQ/fastmcp)** (MCP protocol).

- `ssh_execute` uses `exec_command()` for clean structured output with real exit codes
- `ssh_shell_*` uses `invoke_shell()` for persistent interactive sessions
- All blocking Paramiko calls run in `run_in_executor` to stay async
- Shell keeps a 500KB rolling buffer for `shell_read` polling

## License

MIT
