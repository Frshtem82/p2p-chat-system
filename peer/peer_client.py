"""
High-level STUN client for peers.

This is a thin wrapper around shared.network_utils.STUNClientHTTP
that returns user-friendly result objects (instead of raw HTTP responses).

Design goals:
- No printing (that's the UI layer's job)
- No exceptions leaking (all errors returned as result objects)
- Consistent return types (PeerClientResult)
- Uses only stdlib (urllib) so it works without external deps
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

# Use the low-level client from shared
from shared.network_utils import STUNClientHTTP
from shared.constants import HTTPStatus


# ─────────────────────────────────────────────────────────────────────────────
# Result Object
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PeerClientResult:
    """
    Result of a STUN client operation.
    
    Attributes:
        success: True if the operation succeeded (2xx status).
        status: HTTP status code, or None if connection failed.
        data: Response body (parsed JSON) if any.
        error: Human-readable error message if success=False.
    """
    success: bool
    status: Optional[int] = None
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    
    @classmethod
    def from_response(cls, status: Optional[int],
                      response: Optional[Dict[str, Any]],
                      success_codes: tuple = (200, 201)) -> "PeerClientResult":
        """Build a result from a raw HTTP response."""
        if status is None:
            return cls(
                success=False,
                status=None,
                error="Could not connect to STUN server",
            )
        
        if status in success_codes:
            return cls(success=True, status=status, data=response)
        
        # Extract error message from response
        error_msg = "Unknown error"
        if response:
            error_msg = (
                response.get("error")
                or response.get("message")
                or error_msg
            )
        
        # Add friendly hint for common errors
        if status == HTTPStatus.CONFLICT:
            error_msg = f"Username already taken ({error_msg})"
        elif status == HTTPStatus.NOT_FOUND:
            error_msg = f"Peer not found ({error_msg})"
        
        return cls(success=False, status=status, data=response, error=error_msg)


# ─────────────────────────────────────────────────────────────────────────────
# High-Level STUN Client
# ─────────────────────────────────────────────────────────────────────────────

class PeerSTUNClient:
    """
    High-level client for the STUN server.
    
    All methods return PeerClientResult. No printing, no exceptions.
    
    Usage:
        client = PeerSTUNClient("http://localhost:8000")
        result = client.register("alice", "192.168.1.5", 9000)
        if result.success:
            print("Registered!")
        else:
            print(f"Failed: {result.error}")
    """
    
    def __init__(self, stun_url: str, timeout: int = 10):
        """
        Args:
            stun_url: Base URL of the STUN server (e.g. "http://localhost:8000")
            timeout: Request timeout in seconds
        """
        self.stun_url = stun_url.rstrip("/")
        self._http = STUNClientHTTP(self.stun_url, timeout=timeout)
    
    # ─────────────────────────────────────────────────────────────────────
    # Register / Unregister
    # ─────────────────────────────────────────────────────────────────────
    
    def register(self, username: str, ip: str, port: int) -> PeerClientResult:
        """
        Register this peer with the STUN server.
        
        Returns:
            PeerClientResult with success=True on 201 Created.
        """
        status, response = self._http.register(username, ip, port)
        return PeerClientResult.from_response(
            status, response, success_codes=(201,)
        )
    
    def unregister(self, username: str) -> PeerClientResult:
        """
        Unregister a peer (best-effort).
        
        Returns:
            PeerClientResult. May fail if the server doesn't support /unregister.
        """
        status, response = self._http.unregister(username)
        return PeerClientResult.from_response(
            status, response, success_codes=(200,)
        )
    
    # ─────────────────────────────────────────────────────────────────────
    # Queries
    # ─────────────────────────────────────────────────────────────────────
    
    def list_peers(self, exclude: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get list of all registered peers.
        
        Args:
            exclude: Optional username to exclude from the list (usually self).
        
        Returns:
            List of peer dicts. Empty list on error.
        """
        status, response = self._http.get_peers()
        if status != 200 or not response:
            return []
        
        peers = response.get("peers", [])
        if exclude:
            peers = [p for p in peers if p.get("username") != exclude]
        return peers
    
    def get_peer(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Get info for a specific peer.
        
        Returns:
            Peer dict, or None if not found / error.
        """
        status, response = self._http.get_peer_info(username)
        if status == 200 and response:
            return response
        return None
    
    def get_peer_result(self, username: str) -> PeerClientResult:
        """
        Same as get_peer but returns a full result object.
        Useful when you need to display the error.
        """
        status, response = self._http.get_peer_info(username)
        return PeerClientResult.from_response(
            status, response, success_codes=(200,)
        )
    
    # ─────────────────────────────────────────────────────────────────────
    # Convenience
    # ─────────────────────────────────────────────────────────────────────
    
    def ping(self) -> bool:
        """Check if the STUN server is reachable."""
        status, _ = self._http.get_peers()
        return status is not None
    
    def __repr__(self) -> str:
        return f"PeerSTUNClient({self.stun_url})"