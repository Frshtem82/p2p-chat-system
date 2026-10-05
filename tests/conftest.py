"""
Pytest fixtures shared across all tests.

Provides:
- A running STUN server (in-memory) for integration tests
- A free port finder
- A peer factory
"""

import pytest
import socket
import threading
import time
import sys
import os

# Ensure project root is on path
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from http.server import ThreadingHTTPServer
from stun_server.handler import STUNHandler
from stun_server.storage import MemoryStorage


# ─────────────────────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────────────────────

def find_free_port() -> int:
    """Find a free TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# ─────────────────────────────────────────────────────────────────────────────
# STUN Server Fixture
# ─────────────────────────────────────────────────────────────────────────────

class STUNServerFixture:
    """A running STUN server on a random port (in-memory storage)."""
    
    def __init__(self):
        self.port = find_free_port()
        self.storage = MemoryStorage()
        # Attach storage to handler
        STUNHandler.storage = self.storage
        self.server = ThreadingHTTPServer(("127.0.0.1", self.port), STUNHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        # Wait for server to be ready
        self._wait_ready()
    
    def _wait_ready(self, timeout: float = 3.0) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", self.port), timeout=0.5):
                    return
            except OSError:
                time.sleep(0.05)
        raise RuntimeError("STUN server did not start in time")
    
    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"
    
    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture(scope="function")
def stun_server():
    """Fixture: a fresh STUN server per test."""
    srv = STUNServerFixture()
    try:
        yield srv
    finally:
        srv.stop()


@pytest.fixture(scope="function")
def stun_url(stun_server) -> str:
    """Convenience: just the URL."""
    return stun_server.url


# ─────────────────────────────────────────────────────────────────────────────
# HTTP helper (stdlib only)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def http():
    """Return a simple HTTP helper for tests."""
    import urllib.request
    import urllib.error
    import json
    
    class HTTPHelper:
        @staticmethod
        def get(url: str):
            try:
                with urllib.request.urlopen(url, timeout=5) as r:
                    return r.getcode(), json.loads(r.read().decode())
            except urllib.error.HTTPError as e:
                try:
                    body = json.loads(e.read().decode())
                except Exception:
                    body = {}
                return e.code, body
            except Exception:
                return None, None
        
        @staticmethod
        def post(url: str, data: dict):
            body = json.dumps(data).encode()
            req = urllib.request.Request(
                url, data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=5) as r:
                    return r.getcode(), json.loads(r.read().decode())
            except urllib.error.HTTPError as e:
                try:
                    body = json.loads(e.read().decode())
                except Exception:
                    body = {}
                return e.code, body
            except Exception:
                return None, None
    
    return HTTPHelper


# ─────────────────────────────────────────────────────────────────────────────
# Free port
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def free_port() -> int:
    return find_free_port()