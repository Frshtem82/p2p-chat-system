"""
Protocol constants for P2P Chat System.

Centralizes all magic numbers and strings so they can be changed in one place.
"""

# ─────────────────────────────────────────────────────────────────────────────
# Network
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_TCP_PORT = 9000
DEFAULT_STUN_URL = "http://localhost:8000"
DEFAULT_HOST = "0.0.0.0"

# Socket timeouts (seconds)
SOCKET_TIMEOUT = 1.0           # For non-blocking accept loops
CONNECTION_TIMEOUT = 15.0      # For connecting to a peer
RECV_TIMEOUT = 10.0            # For receiving initial handshake
STUN_REQUEST_TIMEOUT = 10      # For HTTP requests to STUN server

# Buffer sizes
HANDSHAKE_BUFFER = 4096        # For initial connection requests
RECV_BUFFER = 65536            # For ongoing chat messages

# Server
MAX_PENDING_CONNECTIONS = 5

# ─────────────────────────────────────────────────────────────────────────────
# File Transfer
# ─────────────────────────────────────────────────────────────────────────────

CHUNK_SIZE = 8192              # 8 KB chunks
FILE_HASH_ALGORITHM = "sha256"
RECEIVED_FILES_DIR = "received_files"
CHUNK_DELAY = 0.001            # Small delay between chunks (seconds)

# ─────────────────────────────────────────────────────────────────────────────
# Message Types (Protocol)
# ─────────────────────────────────────────────────────────────────────────────

class MessageType:
    """All valid message types in the P2P protocol."""
    
    # Connection lifecycle
    CONNECTION_REQUEST = "connection_request"
    CONNECTION_RESPONSE = "connection_response"
    DISCONNECT = "disconnect"
    KEEP_ALIVE = "keep_alive"
    
    # Chat
    CHAT_MESSAGE = "chat_message"
    
    # File transfer
    FILE_INIT = "file_init"
    FILE_CHUNK = "file_chunk"
    FILE_COMPLETE = "file_complete"
    
    @classmethod
    def all(cls):
        """Return all valid message types."""
        return {
            v for k, v in vars(cls).items()
            if not k.startswith('_') and isinstance(v, str)
        }


# ─────────────────────────────────────────────────────────────────────────────
# STUN Server Endpoints
# ─────────────────────────────────────────────────────────────────────────────

class STUNEndpoint:
    """STUN server HTTP endpoints."""
    
    REGISTER = "/register"
    PEERS = "/peers"
    PEER_INFO = "/peerinfo"
    UNREGISTER = "/unregister"  # Optional, may not be implemented


# ─────────────────────────────────────────────────────────────────────────────
# STUN Server Response Codes
# ─────────────────────────────────────────────────────────────────────────────

class HTTPStatus:
    """HTTP status codes used by STUN server."""
    
    OK = 200
    CREATED = 201
    BAD_REQUEST = 400
    NOT_FOUND = 404
    CONFLICT = 409
    INTERNAL_ERROR = 500


# ─────────────────────────────────────────────────────────────────────────────
# UI / Display
# ─────────────────────────────────────────────────────────────────────────────

class Colors:
    """ANSI colors for terminal output."""
    
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    GRAY = "\033[90m"