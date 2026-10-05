"""
Network utility functions.

Common helpers for socket operations, IP detection, and safe send/recv.
"""

import socket
import json
import urllib.request
import urllib.error
from typing import Optional, Tuple, Dict, Any

from .constants import STUN_REQUEST_TIMEOUT
from .protocol import encode_message, MessageBuffer


# ─────────────────────────────────────────────────────────────────────────────
# IP Detection
# ─────────────────────────────────────────────────────────────────────────────

def get_local_ip() -> str:
    """
    Detect the local IP address.
    
    Uses the trick of connecting a UDP socket to a public address
    (doesn't actually send anything, just determines the outgoing interface).
    
    Returns:
        Local IP as string, or "127.0.0.1" if detection fails.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2.0)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# ─────────────────────────────────────────────────────────────────────────────
# Safe Socket Operations
# ─────────────────────────────────────────────────────────────────────────────

def send_json(sock: socket.socket, data: Dict[str, Any]) -> bool:
    """
    Send a JSON message over a socket with newline delimiter.
    
    Args:
        sock: Connected socket
        data: Message dict
        
    Returns:
        True on success, False on error
    """
    try:
        sock.sendall(encode_message(data))
        return True
    except (socket.error, OSError):
        return False


def recv_until_newline(sock: socket.socket, buffer: MessageBuffer,
                       timeout: float = 10.0) -> Optional[Dict[str, Any]]:
    """
    Receive data until a complete message is available.
    
    Args:
        sock: Connected socket
        buffer: MessageBuffer to accumulate data
        timeout: Total time to wait
        
    Returns:
        First complete message received, or None on timeout/error
    """
    sock.settimeout(timeout)
    try:
        while True:
            messages = buffer.extract_messages()
            if messages:
                return messages[0]
            
            data = sock.recv(4096)
            if not data:
                return None
            buffer.add_data(data)
    except (socket.timeout, socket.error, OSError):
        return None


# ─────────────────────────────────────────────────────────────────────────────
# TCP Connection Helpers
# ─────────────────────────────────────────────────────────────────────────────

def create_server_socket(port: int, host: str = "0.0.0.0",
                         backlog: int = 5) -> Optional[socket.socket]:
    """
    Create and bind a TCP server socket.
    
    Args:
        port: Port to listen on
        host: Host to bind to (default: all interfaces)
        backlog: Listen backlog
        
    Returns:
        Bound socket, or None on error
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        sock.listen(backlog)
        return sock
    except (socket.error, OSError):
        return None


def create_client_socket(timeout: float = 15.0) -> socket.socket:
    """
    Create a TCP client socket with timeout.
    
    Args:
        timeout: Connection timeout in seconds
        
    Returns:
        Unconnected socket
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    return sock


def close_socket(sock: Optional[socket.socket]) -> None:
    """Safely close a socket, ignoring errors."""
    if sock is None:
        return
    try:
        sock.close()
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# STUN Server HTTP Client (stdlib only - no external deps)
# ─────────────────────────────────────────────────────────────────────────────

class STUNClientHTTP:
    """
    Minimal HTTP client for the STUN server using urllib.
    
    No external dependencies.
    Used by peer_core.py (terminal + GUI core).
    """
    
    def __init__(self, base_url: str, timeout: int = STUN_REQUEST_TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
    
    def _request(self, method: str, endpoint: str,
                 data: Optional[Dict[str, Any]] = None
                 ) -> Tuple[Optional[int], Optional[Dict[str, Any]]]:
        """Make an HTTP request. Returns (status_code, response_dict)."""
        url = f"{self.base_url}{endpoint}"
        headers = {"Content-Type": "application/json"}
        body = json.dumps(data).encode("utf-8") if data else None
        
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                status = resp.getcode()
                body = json.loads(resp.read().decode("utf-8"))
                return status, body
        except urllib.error.HTTPError as e:
            try:
                body = json.loads(e.read().decode("utf-8"))
            except Exception:
                body = {"error": str(e)}
            return e.code, body
        except urllib.error.URLError:
            return None, None
        except Exception:
            return None, None
    
    def register(self, username: str, ip: str, port: int
                 ) -> Tuple[Optional[int], Optional[Dict[str, Any]]]:
        """Register a peer with the STUN server."""
        return self._request("POST", "/register", {
            "username": username,
            "ip": ip,
            "port": port,
        })
    
    def get_peers(self) -> Tuple[Optional[int], Optional[Dict[str, Any]]]:
        """Get list of all peers."""
        return self._request("GET", "/peers")
    
    def get_peer_info(self, username: str
                      ) -> Tuple[Optional[int], Optional[Dict[str, Any]]]:
        """Get info for a specific peer."""
        from urllib.parse import quote
        return self._request("GET", f"/peerinfo?username={quote(username)}")
    
    def unregister(self, username: str
                   ) -> Tuple[Optional[int], Optional[Dict[str, Any]]]:
        """Unregister a peer (if server supports it)."""
        return self._request("POST", "/unregister", {"username": username})