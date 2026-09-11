"""Optional process-level network guard for documented offline runs."""

from __future__ import annotations

import os
import socket
from dataclasses import dataclass
from typing import Any


_ACTIVE = False


@dataclass
class _GuardToken:
    socket_class: type[socket.socket]
    create_connection: Any
    getaddrinfo: Any


def offline_requested() -> bool:
    return os.environ.get("BOOK_REPRO_OFFLINE", "").strip() == "1"


def offline_active() -> bool:
    return _ACTIVE


def activate_offline_guard() -> _GuardToken | None:
    """Deny Python socket resolution and connections when explicitly requested.

    Docker runs additionally use ``--network none``.  On Windows this guard is
    the package-level enforcement used after the local wheel environment has
    been prepared; it does not modify the host firewall.
    """
    global _ACTIVE
    if not offline_requested() or _ACTIVE:
        return None
    token = _GuardToken(socket.socket, socket.create_connection, socket.getaddrinfo)

    class OfflineSocket(token.socket_class):
        def connect(self, *args: Any, **kwargs: Any) -> Any:
            raise PermissionError("Network disabled by BOOK_REPRO_OFFLINE=1")

        def connect_ex(self, *args: Any, **kwargs: Any) -> Any:
            raise PermissionError("Network disabled by BOOK_REPRO_OFFLINE=1")

    def denied(*args: Any, **kwargs: Any) -> Any:
        raise PermissionError("Network disabled by BOOK_REPRO_OFFLINE=1")

    socket.socket = OfflineSocket
    socket.create_connection = denied
    socket.getaddrinfo = denied
    _ACTIVE = True
    return token


def restore_offline_guard(token: _GuardToken | None) -> None:
    global _ACTIVE
    if token is None:
        return
    socket.socket = token.socket_class
    socket.create_connection = token.create_connection
    socket.getaddrinfo = token.getaddrinfo
    _ACTIVE = False
