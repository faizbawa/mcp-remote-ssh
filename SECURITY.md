# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.3.x   | Yes       |
| 0.2.x   | Security fixes only |
| < 0.2   | No        |

## Reporting a Vulnerability

If you discover a security vulnerability in mcp-remote-ssh, please report it responsibly:

1. **Do NOT open a public GitHub issue** for security vulnerabilities.
2. Email the maintainer directly: **mbawa@redhat.com**
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

You should receive an acknowledgement within 48 hours. A fix will be developed privately and released as a patch version before public disclosure.

## Security Model

This MCP server provides SSH access to remote hosts for AI agents. The security design:

- **Secret redaction**: Loaded secrets are automatically stripped from all tool responses (literal match only)
- **Stdin injection**: Secrets are fed to exec channels via stdin, not command-line arguments (invisible to `ps aux`)
- **Shell builtins**: Interactive shell injection uses `read`/`export` builtins (no child process spawned)
- **Local file only**: Secret env files are read from the MCP server's local filesystem, never from the remote host

### Known Limitations

- Redaction is literal-match only — encoding/transformation attacks (base64, rev, hex) bypass it
- `AutoAddPolicy` is used for SSH host keys (accepts unknown hosts without verification) — intentional for ephemeral lab environments
- An adversarial LLM that deliberately tries to exfiltrate secrets is out of scope for MCP-layer defenses

## Dependencies

- [Paramiko](https://www.paramiko.org/) — SSH protocol implementation
- [FastMCP](https://github.com/PrefectHQ/fastmcp) — MCP protocol framework

Both are actively maintained with security disclosure processes of their own.
