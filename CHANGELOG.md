# Changelog

## 0.2.2 (2026-06-23)

### Fixes

- Removed `License :: OSI Approved :: MIT License` classifier that conflicts with PEP 639 `license` field — PyPI reads license from `license = "MIT"` directly

## 0.2.1 (2026-06-23)

### Fixes

- (yanked) Attempted license classifier — breaks build under PEP 639

## 0.2.0 (2026-06-23)

### Features

- **Secret-safe environment variables** -- `ssh_load_env_file` reads secrets from a local `.env` file, injects them into the remote session via shell builtins (no process tree exposure), and registers values for automatic output redaction across all tools
- **Automatic output redaction** -- all tool responses (`ssh_execute`, `ssh_shell_send`, `ssh_shell_read`, `ssh_read_remote_file`, etc.) are scrubbed of loaded secret values before reaching the LLM, replacing them with `***`
- **Longest-first redaction** -- prevents partial-match corruption when one secret is a substring of another
- **Exec channel injection** -- loaded secrets are automatically prepended as exports to `ssh_execute` commands, making them available even in stateless exec channels
- **Shell auto-injection** -- if `ssh_shell_open` is called after secrets are loaded, they are automatically exported into the new shell
- **`ssh_clear_secrets`** -- clear the redaction registry when secrets are no longer needed

## 0.1.0 (2026-03-17)

Initial release.

### Features

- **Connection management** -- `ssh_connect` with password, key, and SSH agent authentication
- **Structured execution** -- `ssh_execute` and `ssh_sudo_execute` returning `{stdout, stderr, exit_code}`
- **Interactive shell** -- persistent `invoke_shell` sessions with `ssh_shell_open`, `ssh_shell_send`, `ssh_shell_read`, `ssh_shell_send_control`, and `ssh_shell_wait`
- **SFTP file transfer** -- `ssh_upload_file`, `ssh_download_file`, `ssh_read_remote_file`, `ssh_write_remote_file`, `ssh_list_remote_dir`
- **Port forwarding** -- `ssh_forward_port`, `ssh_list_forwards`, `ssh_close_forward`
- **Transport options** -- stdio, SSE, and Streamable HTTP via `--transport` flag
