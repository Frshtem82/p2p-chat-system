"""
Shared modules for P2P Chat System.

This package contains code used by both:
- peer/peer.py (terminal version)
- gui/app.py (GUI version)

It provides:
- constants: Protocol constants and message types
- protocol: Message serialization/deserialization
- file_transfer: File hashing, chunking, and size formatting
- network_utils: Network helper functions
- peer_core: The core PeerNode class with all P2P logic
"""

__version__ = "1.0.0"
__all__ = [
    "constants",
    "protocol",
    "file_transfer",
    "network_utils",
    "peer_core",
]