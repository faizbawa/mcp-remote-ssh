from __future__ import annotations

import asyncio
import socket
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import paramiko
from loguru import logger


@dataclass
class PortForward:
    forward_id: str
    local_port: int
    remote_host: str
    remote_port: int
    server: paramiko.Transport | None = field(default=None, repr=False)
    _thread: threading.Thread | None = field(default=None, repr=False)
    _stop_event: threading.Event = field(default_factory=threading.Event, repr=False)
    _server_socket: socket.socket | None = field(default=None, repr=False)

    def summary(self) -> dict[str, Any]:
        return {
            'forward_id': self.forward_id,
            'local_port': self.local_port,
            'remote_host': self.remote_host,
            'remote_port': self.remote_port,
        }


@dataclass
class SSHSession:
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    host: str = ''
    username: str = ''
    port: int = 22
    connected_at: float = field(default_factory=time.time)

    client: paramiko.SSHClient = field(default_factory=paramiko.SSHClient, repr=False)
    _shell_channel: paramiko.Channel | None = field(default=None, repr=False)
    _shell_buffer: str = field(default='', repr=False)
    _sftp: paramiko.SFTPClient | None = field(default=None, repr=False)
    _forwards: dict[str, PortForward] = field(default_factory=dict, repr=False)

    @property
    def is_connected(self) -> bool:
        transport = self.client.get_transport()
        return transport is not None and transport.is_active()

    @property
    def has_shell(self) -> bool:
        return self._shell_channel is not None and not self._shell_channel.closed

    @property
    def sftp(self) -> paramiko.SFTPClient:
        if self._sftp is None or self._sftp.get_channel().closed:
            self._sftp = self.client.open_sftp()
        return self._sftp

    def shell_open(self, term: str = 'xterm', width: int = 200, height: int = 50) -> None:
        if self.has_shell:
            return
        self._shell_channel = self.client.invoke_shell(term=term, width=width, height=height)
        self._shell_channel.settimeout(0.1)
        self._shell_buffer = ''

    def shell_send(self, data: str) -> None:
        if not self.has_shell:
            msg = 'No interactive shell open. Call shell_open first.'
            raise RuntimeError(msg)
        self._shell_channel.sendall(data.encode())

    def shell_read(self, max_bytes: int = 65536) -> str:
        if not self.has_shell:
            msg = 'No interactive shell open. Call shell_open first.'
            raise RuntimeError(msg)
        chunks: list[str] = []
        while self._shell_channel.recv_ready():
            try:
                data = self._shell_channel.recv(max_bytes)
                if data:
                    chunks.append(data.decode(errors='replace'))
            except socket.timeout:
                break
        new_data = ''.join(chunks)
        self._shell_buffer += new_data
        if len(self._shell_buffer) > 500_000:
            self._shell_buffer = self._shell_buffer[-500_000:]
        return new_data

    def shell_read_buffer(self, lines: int = 100) -> str:
        self.shell_read()
        all_lines = self._shell_buffer.splitlines()
        tail = all_lines[-lines:] if len(all_lines) > lines else all_lines
        return '\n'.join(tail)

    def summary(self) -> dict[str, Any]:
        uptime = int(time.time() - self.connected_at)
        return {
            'session_id': self.session_id,
            'host': self.host,
            'username': self.username,
            'port': self.port,
            'connected': self.is_connected,
            'shell_open': self.has_shell,
            'uptime_seconds': uptime,
            'active_forwards': len(self._forwards),
        }

    def close(self) -> list[str]:
        """Close all resources. Returns list of warnings for any failures."""
        errors: list[str] = []

        for fwd_id, fwd in list(self._forwards.items()):
            try:
                fwd._stop_event.set()
                if fwd._server_socket:
                    fwd._server_socket.close()
                if fwd._thread and fwd._thread.is_alive():
                    fwd._thread.join(timeout=2)
            except Exception as e:  # noqa: BLE001
                errors.append(f'Forward {fwd_id}: {e}')
        self._forwards.clear()

        if self._sftp is not None:
            try:
                self._sftp.close()
            except Exception as e:  # noqa: BLE001
                errors.append(f'SFTP: {e}')
            self._sftp = None

        if self._shell_channel is not None:
            try:
                self._shell_channel.close()
            except Exception as e:  # noqa: BLE001
                errors.append(f'Shell: {e}')
            self._shell_channel = None

        try:
            self.client.close()
        except Exception as e:  # noqa: BLE001
            errors.append(f'SSH: {e}')

        if errors:
            logger.warning(f'Session {self.session_id} close warnings: {"; ".join(errors)}')
        return errors


class SessionStore:
    """Thread-safe store for active SSH sessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, SSHSession] = {}
        self._lock = asyncio.Lock()

    async def add(self, session: SSHSession) -> None:
        async with self._lock:
            self._sessions[session.session_id] = session

    def get(self, session_id: str) -> SSHSession:
        session = self._sessions.get(session_id)
        if session is None:
            available = ', '.join(self._sessions.keys()) or 'none'
            msg = f'Session not found: {session_id}. Active sessions: {available}. Use ssh_list_sessions to see details.'
            raise ValueError(msg)
        return session

    async def remove(self, session_id: str) -> SSHSession | None:
        async with self._lock:
            return self._sessions.pop(session_id, None)

    def list_all(self) -> list[dict[str, Any]]:
        return [s.summary() for s in self._sessions.values()]

    def __len__(self) -> int:
        return len(self._sessions)
