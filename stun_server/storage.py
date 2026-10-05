"""
Storage backends for the STUN server.

Provides a common interface with two implementations:
- MemoryStorage: in-process dictionary (no dependencies)
- RedisStorage: persistent Redis backend (requires `redis` package)

Both implement the same interface, so the handler doesn't care which is used.
"""

import threading
from typing import Dict, List, Optional, Any


# ─────────────────────────────────────────────────────────────────────────────
# Base Interface
# ─────────────────────────────────────────────────────────────────────────────

class BaseStorage:
    """
    Abstract storage interface.
    
    All methods return plain dicts (JSON-serializable).
    """
    
    def add_peer(self, username: str, ip: str, port: int) -> bool:
        """Add a peer. Returns False if username exists."""
        raise NotImplementedError
    
    def get_all_peers(self) -> List[Dict[str, Any]]:
        """Return list of all peer dicts."""
        raise NotImplementedError
    
    def get_peer(self, username: str) -> Optional[Dict[str, Any]]:
        """Return peer dict or None."""
        raise NotImplementedError
    
    def remove_peer(self, username: str) -> bool:
        """Remove a peer. Returns False if not found."""
        raise NotImplementedError
    
    def peer_exists(self, username: str) -> bool:
        """Check if a username is registered."""
        raise NotImplementedError
    
    def count(self) -> int:
        """Number of registered peers."""
        raise NotImplementedError
    
    def clear(self) -> None:
        """Remove all peers."""
        raise NotImplementedError
    
    @property
    def name(self) -> str:
        """Human-readable backend name."""
        raise NotImplementedError


# ─────────────────────────────────────────────────────────────────────────────
# In-Memory Storage
# ─────────────────────────────────────────────────────────────────────────────

class MemoryStorage(BaseStorage):
    """
    In-memory storage using a dict.
    
    Thread-safe with a lock (safe with ThreadingHTTPServer).
    Data is lost when the server stops.
    """
    
    def __init__(self):
        self._peers: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        print("[*] Using IN-MEMORY storage")
    
    def add_peer(self, username: str, ip: str, port: int) -> bool:
        with self._lock:
            if username in self._peers:
                return False
            self._peers[username] = {
                "username": username,
                "ip": ip,
                "port": int(port),
            }
            return True
    
    def get_all_peers(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [dict(p) for p in self._peers.values()]
    
    def get_peer(self, username: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            peer = self._peers.get(username)
            return dict(peer) if peer else None
    
    def remove_peer(self, username: str) -> bool:
        with self._lock:
            if username in self._peers:
                del self._peers[username]
                return True
            return False
    
    def peer_exists(self, username: str) -> bool:
        with self._lock:
            return username in self._peers
    
    def count(self) -> int:
        with self._lock:
            return len(self._peers)
    
    def clear(self) -> None:
        with self._lock:
            self._peers.clear()
    
    @property
    def name(self) -> str:
        return "In-Memory"


# ─────────────────────────────────────────────────────────────────────────────
# Redis Storage
# ─────────────────────────────────────────────────────────────────────────────

class RedisStorage(BaseStorage):
    """
    Redis-backed storage.
    
    Data structure:
        peers_set            -> Set of usernames
        peer:<username>      -> Hash {username, ip, port}
    
    Thread-safe by design (Redis handles concurrency).
    """
    
    def __init__(self, host: str = "localhost", port: int = 6379,
                 db: int = 0, clear_on_start: bool = True):
        import redis  # Import here so MemoryStorage works without redis
        
        self._redis = redis.Redis(
            host=host, port=port, db=db,
            decode_responses=True,
            socket_connect_timeout=3,
        )
        # Test connection (raises if Redis is down)
        self._redis.ping()
        
        if clear_on_start:
            self._clear_all()
        
        print(f"[*] Using REDIS storage ({host}:{port}, db={db})")
    
    def _clear_all(self) -> None:
        """Delete all peers_set and peer:* keys."""
        for key in self._redis.scan_iter("peer:*"):
            self._redis.delete(key)
        self._redis.delete("peers_set")
    
    def add_peer(self, username: str, ip: str, port: int) -> bool:
        if self._redis.sismember("peers_set", username):
            return False
        # Use a pipeline to make the two writes atomic-ish
        pipe = self._redis.pipeline()
        pipe.hset(f"peer:{username}", mapping={
            "username": username,
            "ip": ip,
            "port": str(port),
        })
        pipe.sadd("peers_set", username)
        pipe.execute()
        return True
    
    def get_all_peers(self) -> List[Dict[str, Any]]:
        usernames = self._redis.smembers("peers_set")
        if not usernames:
            return []
        
        pipe = self._redis.pipeline()
        for u in usernames:
            pipe.hgetall(f"peer:{u}")
        results = pipe.execute()
        
        peers = []
        for data in results:
            if data:
                data["port"] = int(data["port"])
                peers.append(data)
        return peers
    
    def get_peer(self, username: str) -> Optional[Dict[str, Any]]:
        if not self._redis.sismember("peers_set", username):
            return None
        data = self._redis.hgetall(f"peer:{username}")
        if not data:
            return None
        data["port"] = int(data["port"])
        return data
    
    def remove_peer(self, username: str) -> bool:
        if not self._redis.sismember("peers_set", username):
            return False
        pipe = self._redis.pipeline()
        pipe.delete(f"peer:{username}")
        pipe.srem("peers_set", username)
        pipe.execute()
        return True
    
    def peer_exists(self, username: str) -> bool:
        return bool(self._redis.sismember("peers_set", username))
    
    def count(self) -> int:
        return self._redis.scard("peers_set")
    
    def clear(self) -> None:
        self._clear_all()
    
    @property
    def name(self) -> str:
        return "Redis"


# ─────────────────────────────────────────────────────────────────────────────
# Factory
# ─────────────────────────────────────────────────────────────────────────────

def create_storage(use_redis: bool = True,
                   redis_host: str = "localhost",
                   redis_port: int = 6379,
                   redis_db: int = 0,
                   clear_on_start: bool = True) -> BaseStorage:
    """
    Create a storage backend.
    
    Tries Redis first (if use_redis=True). Falls back to MemoryStorage
    on any connection error.
    """
    if use_redis:
        try:
            return RedisStorage(
                host=redis_host, port=redis_port, db=redis_db,
                clear_on_start=clear_on_start,
            )
        except ImportError:
            print("[!] 'redis' package not installed. Falling back to memory.")
        except Exception as e:
            print(f"[!] Redis not available ({e}). Falling back to memory.")
    
    return MemoryStorage()