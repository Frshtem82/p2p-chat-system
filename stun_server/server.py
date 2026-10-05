"""
STUN Server entry point.

Usage:
    python server.py                          # Default: 0.0.0.0:8000, try Redis
    python server.py --port 9000              # Custom port
    python server.py --no-redis               # Force in-memory
    python server.py --keep-redis-data        # Don't clear Redis on start
    python server.py 9000                     # Legacy positional port
"""

from http.server import HTTPServer, ThreadingHTTPServer
import sys

from .config import ServerConfig, parse_args
from .storage import create_storage, BaseStorage
from .handler import STUNHandler


def print_banner(config: ServerConfig, storage: BaseStorage) -> None:
    """Print a startup banner."""
    line = "=" * 60
    print(f"\n{line}")
    print(f"  STUN Server")
    print(f"{line}")
    print(f"  Listening on: http://{config.host}:{config.port}")
    print(f"  Storage:      {storage.name}")
    print(f"  Threaded:     {'yes' if config.threaded else 'no'}")
    print(f"{line}")
    print(f"  Endpoints:")
    print(f"    POST /register     - Register a peer")
    print(f"    POST /unregister   - Remove a peer")
    print(f"    GET  /peers        - List all peers")
    print(f"    GET  /peerinfo     - Get peer info (?username=...)")
    print(f"    GET  /health       - Health check")
    print(f"{line}\n")


def create_http_server(config: ServerConfig, handler_class) -> HTTPServer:
    """Create the HTTP server (threaded or not)."""
    server_cls = ThreadingHTTPServer if config.threaded else HTTPServer
    try:
        return server_cls((config.host, config.port), handler_class)
    except OSError as e:
        print(f"[-] Failed to bind {config.host}:{config.port}: {e}")
        sys.exit(1)


def run(config: ServerConfig) -> None:
    """Run the STUN server."""
    # Create storage (tries Redis, falls back to memory)
    storage = create_storage(
        use_redis=config.use_redis,
        redis_host=config.redis_host,
        redis_port=config.redis_port,
        redis_db=config.redis_db,
        clear_on_start=config.clear_redis_on_start,
    )
    
    # Attach storage to handler class
    STUNHandler.storage = storage
    
    # Create and run server
    server = create_http_server(config, STUNHandler)
    print_banner(config, storage)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Shutting down...")
    finally:
        server.server_close()
        print("[*] Server stopped.")


def main(argv=None) -> None:
    config = parse_args(argv)
    run(config)


if __name__ == "__main__":
    main()