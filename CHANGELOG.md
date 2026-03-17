# Changelog

## 0.1.0 (2026-03-17)

Initial release.

### Features

- **Connection management** -- `ssh_connect` with password, key, and SSH agent authentication
- **Structured execution** -- `ssh_execute` and `ssh_sudo_execute` returning `{stdout, stderr, exit_code}`
- **Interactive shell** -- persistent `invoke_shell` sessions with `ssh_shell_open`, `ssh_shell_send`, `ssh_shell_read`, `ssh_shell_send_control`, and `ssh_shell_wait`
- **SFTP file transfer** -- `ssh_upload_file`, `ssh_download_file`, `ssh_read_remote_file`, `ssh_write_remote_file`, `ssh_list_remote_dir`
- **Port forwarding** -- `ssh_forward_port`, `ssh_list_forwards`, `ssh_close_forward`
- **Transport options** -- stdio, SSE, and Streamable HTTP via `--transport` flag
