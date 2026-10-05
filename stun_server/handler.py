"""
HTTP request handler for the STUN server.

Endpoints:
    POST /register      - Register a peer
    POST /unregister    - Remove a peer (new)
    GET  /peers         - List all peers
    GET  /peerinfo      - Get one peer's info (?username=...)
    GET  /health        - Health check (new)
"""

import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Optional, Dict, Any

from .storage import BaseStorage


# Response messages (avoid typos and centralize)
MSG_OK = "OK"
MSG_REGISTERED = "Registered successfully"
MSG_MISSING_FIELDS = "Missing required fields: username, ip, port"
MSG_USERNAME_EXISTS = "Username already exists"
MSG_NOT_FOUND = "Not Found"
MSG_PEER_NOT_FOUND = "Peer not found"
MSG_MISSING_USERNAME = "Missing 'username' parameter"
MSG_INVALID_JSON = "Invalid JSON body"
MSG_INVALID_PORT = "Port must be an integer between 1 and 65535"


class STUNHandler(BaseHTTPRequestHandler):
    """
    HTTP handler for the STUN server.
    
    The storage backend is attached as a class attribute (set by server.py).
    This is a simple way to share state with the handler.
    """
    
    # Overridden by server.py before starting
    storage: BaseStorage = None
    
    # Silence default per-request logging (we log manually)
    def log_message(self, fmt, *args):
        # Keep it short: only log non-GET requests
        if self.command != "GET":
            print(f"[HTTP] {self.client_address[0]} "
                  f"{self.command} {self.path} -> {args[1]}")
    
    # ─────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────
    
    def _send_json(self, status: int, data: Dict[str, Any]) -> None:
        """Send a JSON response."""
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    
    def _error(self, status: int, message: str) -> None:
        """Send an error response. Uses 'error' key for consistency with README."""
        self._send_json(status, {"error": message})
    
    def _read_json_body(self) -> Optional[Dict[str, Any]]:
        """Read and parse JSON request body. Returns None on failure."""
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length <= 0:
                return None
            body = self.rfile.read(length)
            return json.loads(body.decode("utf-8"))
        except (ValueError, json.JSONDecodeError):
            return None
    
    def _get_query_param(self, name: str) -> Optional[str]:
        """Get a single query string parameter."""
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        values = params.get(name)
        return values[0] if values else None
    
    # ─────────────────────────────────────────────────────────────────────
    # POST
    # ─────────────────────────────────────────────────────────────────────
    
    def do_POST(self) -> None:
        path = urlparse(self.path).path
        
        if path == "/register":
            self._handle_register()
        elif path == "/unregister":
            self._handle_unregister()
        else:
            self._error(404, MSG_NOT_FOUND)
    
    def _handle_register(self) -> None:
        """Handle POST /register."""
        data = self._read_json_body()
        if data is None:
            self._error(400, MSG_INVALID_JSON)
            return
        
        username = data.get("username")
        ip = data.get("ip")
        port = data.get("port")
        
        # Validate presence
        if not username or not ip or port is None:
            self._error(400, MSG_MISSING_FIELDS)
            return
        
        # Validate types
        if not isinstance(username, str) or not isinstance(ip, str):
            self._error(400, MSG_MISSING_FIELDS)
            return
        
        # Validate port
        try:
            port_int = int(port)
            if not (1 <= port_int <= 65535):
                raise ValueError
        except (ValueError, TypeError):
            self._error(400, MSG_INVALID_PORT)
            return
        
        # Try to add
        if self.storage.add_peer(username, ip, port_int):
            print(f"[+] Registered: {username} ({ip}:{port_int})")
            self._send_json(201, {
                "message": MSG_REGISTERED,
                "username": username,
                "ip": ip,
                "port": port_int,
            })
        else:
            self._error(409, MSG_USERNAME_EXISTS)
    
    def _handle_unregister(self) -> None:
        """Handle POST /unregister."""
        data = self._read_json_body()
        if data is None:
            self._error(400, MSG_INVALID_JSON)
            return
        
        username = data.get("username")
        if not username:
            self._error(400, MSG_MISSING_USERNAME)
            return
        
        if self.storage.remove_peer(username):
            print(f"[-] Unregistered: {username}")
            self._send_json(200, {"message": f"Unregistered '{username}'"})
        else:
            self._error(404, MSG_PEER_NOT_FOUND)
    
    # ─────────────────────────────────────────────────────────────────────
    # GET
    # ─────────────────────────────────────────────────────────────────────
    
    def do_GET(self) -> None:
        path = urlparse(self.path).path
        
        if path == "/peers":
            self._handle_peers()
        elif path == "/peerinfo":
            self._handle_peerinfo()
        elif path == "/health":
            self._handle_health()
        else:
            self._error(404, MSG_NOT_FOUND)
    
    def _handle_peers(self) -> None:
        """Handle GET /peers."""
        peers = self.storage.get_all_peers()
        self._send_json(200, {
            "peers": peers,
            "count": len(peers),
        })
    
    def _handle_peerinfo(self) -> None:
        """Handle GET /peerinfo?username=..."""
        username = self._get_query_param("username")
        if not username:
            self._error(400, MSG_MISSING_USERNAME)
            return
        
        peer = self.storage.get_peer(username)
        if peer:
            self._send_json(200, peer)
        else:
            self._error(404, MSG_PEER_NOT_FOUND)
    
    def _handle_health(self) -> None:
        """Handle GET /health. Useful for Docker health checks."""
        self._send_json(200, {
            "status": "ok",
            "backend": self.storage.name,
            "peers": self.storage.count(),
        })