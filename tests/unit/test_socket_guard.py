"""Socket guard self-test (PLAN section 7; must run in CI)."""

import socket

import pytest


def test_socket_guard_blocks_non_loopback() -> None:
    with pytest.raises(OSError, match="network blocked"):
        s = socket.socket()
        try:
            s.connect(("203.0.113.1", 80))
        finally:
            s.close()
