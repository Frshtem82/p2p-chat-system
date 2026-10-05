"""
Server configuration and CLI argument parsing.
"""

import argparse
from dataclasses import dataclass


@dataclass
class ServerConfig:
    """Server configuration."""
    
    host: str = "0.0.0.0"
    port: int = 8000
    use_redis: bool = True
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    clear_redis_on_start: bool = True  # Reset peers on startup
    threaded: bool = True               # Use ThreadingHTTPServer


def parse_args(argv=None) -> ServerConfig:
    """
    Parse command-line arguments.
    
    Usage:
        python server.py [--host HOST] [--port PORT]
                         [--no-redis]
                         [--redis-host HOST] [--redis-port PORT]
                         [--keep-redis-data]
    """
    parser = argparse.ArgumentParser(
        prog="stun_server",
        description="STUN Server for P2P Chat System",
    )
    
    parser.add_argument(
        "--host", default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", type=int, default=8000,
        help="Port to listen on (default: 8000)"
    )
    parser.add_argument(
        "--no-redis", action="store_true",
        help="Force in-memory storage (don't try Redis)"
    )
    parser.add_argument(
        "--redis-host", default="localhost",
        help="Redis host (default: localhost)"
    )
    parser.add_argument(
        "--redis-port", type=int, default=6379,
        help="Redis port (default: 6379)"
    )
    parser.add_argument(
        "--redis-db", type=int, default=0,
        help="Redis database number (default: 0)"
    )
    parser.add_argument(
        "--keep-redis-data", action="store_true",
        help="Don't clear Redis data on startup"
    )
    
    # Legacy support: allow positional port
    # e.g. `python server.py 9000` -> port=9000
    args, unknown = parser.parse_known_args(argv)
    for token in unknown:
        if token.isdigit():
            args.port = int(token)
            break
    
    return ServerConfig(
        host=args.host,
        port=args.port,
        use_redis=not args.no_redis,
        redis_host=args.redis_host,
        redis_port=args.redis_port,
        redis_db=args.redis_db,
        clear_redis_on_start=not args.keep_redis_data,
    )