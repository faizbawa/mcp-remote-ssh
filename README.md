# mcp-remote-ssh

[![PyPI](https://img.shields.io/pypi/v/mcp-remote-ssh.svg)](https://pypi.org/project/mcp-remote-ssh/)
[![Python](https://img.shields.io/pypi/pyversions/mcp-remote-ssh.svg)](https://pypi.org/project/mcp-remote-ssh/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

MCP server giving AI agents full SSH access -- persistent sessions, structured command output, SFTP file transfer, port forwarding, session transcript recording, and **secret-safe environment variable injection with automatic output redaction**.

## Why this exists

Every other SSH MCP server is missing something: no password auth, no persistent sessions, no SFTP, no port forwarding, or no structured exit codes. This one has all of them -- plus the only MCP-level secret management that prevents AI agents from ever seeing your credentials.

## Secret-Safe Environment Variables

**The problem:** When an AI agent needs to use API tokens, passwords, or keys on a remote server, the standard approach exposes secrets in the LLM's context window. The agent either reads the secret file (now it's in the conversation) or runs `echo $TOKEN` and sees the value in the output.

**The solution:** `ssh_load_env_file` reads secrets from a local file on your machine, injects them into the remote SSH session, and registers them for **automatic output redaction**. The AI agent can use the variables freely -- every tool response is scrubbed before it reaches the LLM.

```text
# Agent calls this -- file is read from YOUR machine, not the remote host
ssh_load_env_file(session_id="abc", file_path="~/.secrets/prod.env")
→ "Loaded 3 variables from local:~/.secrets/prod.env: API_TOKEN, DB_PASS, SECRET_KEY"

# Agent tries to echo the value -- redacted automatically
ssh_execute(session_id="abc", command="echo $API_TOKEN")
→ {"stdout": "***\n", "exit_code": 0}

# Agent dumps the environment -- all secret values scrubbed
ssh_execute(session_id="abc", command="env | grep API_TOKEN")
→ {"stdout": "API_TOKEN=***\n", "exit_code": 0}

# Agent reads a file containing a secret -- also redacted
ssh_read_remote_file(session_id="abc", remote_path="/etc/app/config")
→ "db_password=***\ndb_host=localhost\n"

# Normal commands work perfectly -- no over-redaction
ssh_execute(session_id="abc", command="uname -a")
→ {"stdout": "Linux server 6.1.0 ...", "exit_code": 0}
```

### How it works

```
┌─────────┐         ┌──────────────────────────────┐         ┌─────────────┐
│   LLM   │ ←─JSON─ │   MCP Server (your machine)  │ ──SSH─→ │ Remote Host │
│ (Agent) │         │                              │         │             │
└─────────┘         │  1. Reads ~/.secrets/prod.env│         └─────────────┘
                    │  2. Parses KEY=VALUE pairs   │
                    │  3. Stores values in memory  │
                    │  4. Injects into SSH session │
                    │  5. Redacts ALL tool output  │
                    └──────────────────────────────┘
```

1. **Local file read** -- the env file lives on your machine, never on the remote host
2. **Shell injection via builtins** -- uses `read -r VAR <<< 'value' && export VAR` (no process tree exposure)
3. **Stdin-based exec injection** -- `ssh_execute` feeds secrets via stdin to a bash wrapper, so they never appear in `/proc/*/cmdline`
4. **Automatic redaction** -- every tool response (`ssh_execute`, `ssh_shell_send`, `ssh_shell_read`, `ssh_read_remote_file`) is scrubbed before reaching the LLM
5. **Longest-first matching** -- prevents partial-match corruption (e.g., `abc123` is replaced before `abc`)

### Security properties

| Threat | Mitigated? | How |
|--------|-----------|-----|
| Secret in LLM context window | Yes | Output redaction replaces values with `***` |
| Secret in remote process tree (shell) | Yes | Shell builtins (`read`/`export`) don't fork |
| Secret in remote process tree (exec) | Yes | Secrets fed via stdin, never in `/proc/*/cmdline` |
| LLM tries `cat` on the env file | N/A | File is local-only, doesn't exist on remote |
| LLM tries `echo $VAR` | Yes | Output is redacted |
| Encoded/transformed secret (base64) | No | Only literal matches are redacted |
| MITM on first SSH connection | Accepted | `AutoAddPolicy` used — see note below |

### Host key policy

This server uses Paramiko's `AutoAddPolicy` — unknown host keys are accepted without prompting. This is intentional for QE/lab environments where hosts are ephemeral (Beaker, cloud instances, CI machines). The trade-off:

- **Pro:** Zero-friction connections to newly provisioned machines
- **Con:** Vulnerable to MITM on the very first connection to an unknown host

If you operate on untrusted networks, consider wrapping connections through a VPN or SSH bastion with pre-distributed host keys. A `host_key_policy` parameter may be added in a future release for strict environments.

### Env file format

Standard `.env` format:

```bash
# Comments are ignored
API_TOKEN=your-secret-token
DB_PASSWORD="quoted values work"
SECRET_KEY='single quotes too'
export ALSO_WORKS=yes
```

## Session transcripts

Recording is **off by default**. Enable it per session when you need an audit log of what the agent actually ran — useful for bug reproductions and test campaigns.

```text
# Start recording on connect
ssh_connect(host="lab.example.com", username="root", password="...", record=True)

# Or toggle later
ssh_start_recording(session_id="a1b2c3d4")
ssh_execute(session_id="a1b2c3d4", command="uname -a")
ssh_get_transcript(session_id="a1b2c3d4")
→ {"recording": true, "total_entries": 2, "transcript": "[12:01:02] --- connect: lab.example.com ---\n[12:01:05] $ uname -a\nLinux ...\n[exit 0]"}

ssh_save_transcript(session_id="a1b2c3d4", path="/tmp/lab-session.log")
ssh_stop_recording(session_id="a1b2c3d4")
```

- Execute/sudo **output** and shell send/read I/O are secret-redacted before they are recorded
- Closing the session discards the in-memory transcript — `ssh_save_transcript` or `ssh_get_transcript` first

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

## Tools (24)

### Connection

| Tool | Description |
|------|-------------|
| `ssh_connect` | Connect with password, key, or agent auth. Optional `record=True` to start a transcript immediately. Returns `session_id` |
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

### Secrets Management

| Tool | Description |
|------|-------------|
| `ssh_load_env_file` | Load secrets from a local env file; values never returned to the LLM |
| `ssh_clear_secrets` | Clear redaction registry (values become visible again) |

### Transcripts

| Tool | Description |
|------|-------------|
| `ssh_start_recording` | Start recording execute/sudo/shell I/O for this session |
| `ssh_stop_recording` | Stop recording; transcript stays available until the session is closed |
| `ssh_get_transcript` | Return the transcript as text or JSONL (`last_n` optional) |
| `ssh_save_transcript` | Write the transcript to a **local** file on the MCP host |

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
ssh_connect(host="server.example.com", username="admin", password="secret", record=True)
→ {"session_id": "a1b2c3d4", "connected": true, "recording": true}

ssh_load_env_file(session_id="a1b2c3d4", file_path="~/.secrets/prod.env")
→ "Loaded 2 variables: API_TOKEN, DB_PASS"

ssh_execute(session_id="a1b2c3d4", command="curl -H \"Authorization: Bearer $API_TOKEN\" https://api.example.com")
→ {"stdout": "{\"status\": \"ok\"}", "exit_code": 0}  # token used but never visible

ssh_shell_open(session_id="a1b2c3d4")
ssh_shell_send(session_id="a1b2c3d4", data="cd /opt && make -j$(nproc)")
ssh_shell_wait(session_id="a1b2c3d4", pattern="$ ", timeout=600)

ssh_upload_file(session_id="a1b2c3d4", local_path="config.yaml", remote_path="/etc/app/config.yaml")
ssh_forward_port(session_id="a1b2c3d4", remote_port=5432, local_port=15432)
```

## Design

Built on **[Paramiko](https://www.paramiko.org/)** (SSH) + **[FastMCP](https://github.com/PrefectHQ/fastmcp)** (MCP protocol).

- `ssh_execute` uses `exec_command()` for clean structured output with real exit codes
- When secrets are loaded, `ssh_execute` feeds exports via stdin to a `bash` wrapper, then `exec`s the actual command -- secrets never appear in the process tree
- `ssh_shell_*` uses `invoke_shell()` for persistent interactive sessions
- All blocking Paramiko calls run in `run_in_executor` to stay async
- Shell keeps a 500KB rolling buffer for `shell_read` polling
- Secret redaction uses longest-first string replacement across all output paths
- Session transcripts are in-memory, off by default, and discarded when the session is closed

## License

MIT
