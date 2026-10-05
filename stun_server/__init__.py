"""
STUN Server for P2P Chat System.

Central registration and peer discovery service.
Provides HTTP endpoints for peers to register and find each other.

Modules:
    config: Server configuration and CLI argument parsing
    storage: Storage backends (Memory and Redis)
    handler: HTTP request handler
    server: Main entry point
"""

__version__ = "1.0.0"