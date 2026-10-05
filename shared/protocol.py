"""
Message protocol for P2P Chat.

Handles:
- Creating protocol messages (factory methods)
- Serializing/deserializing JSON messages
- Buffering incoming data and extracting complete messages
"""

import json
import time
import threading
from typing import Optional, Dict, Any, List

from .constants import MessageType


# ─────────────────────────────────────────────────────────────────────────────
# Message Factory
# ─────────────────────────────────────────────────────────────────────────────

class Message:
    """
    Factory for creating protocol messages.
    
    All messages are dictionaries with a 'type' field.
    Use these factory methods instead of building dicts manually to ensure consistency.
    """
    
    @staticmethod
    def connection_request(username: str, ip: str, port: int) -> Dict[str, Any]:
        """Create a connection request message."""
        return {
            "type": MessageType.CONNECTION_REQUEST,
            "username": username,
            "ip": ip,
            "port": port,
            "timestamp": time.time(),
        }
    
    @staticmethod
    def connection_response(accepted: bool, username: str,
                            reason: Optional[str] = None) -> Dict[str, Any]:
        """Create a connection response message."""
        msg = {
            "type": MessageType.CONNECTION_RESPONSE,
            "accepted": accepted,
            "username": username,
        }
        if reason:
            msg["reason"] = reason
        return msg
    
    @staticmethod
    def chat_message(username: str, message: str) -> Dict[str, Any]:
        """Create a chat message."""
        return {
            "type": MessageType.CHAT_MESSAGE,
            "username": username,
            "message": message,
            "timestamp": time.time(),
        }
    
    @staticmethod
    def disconnect(username: str, reason: Optional[str] = None) -> Dict[str, Any]:
        """Create a disconnect message."""
        msg = {
            "type": MessageType.DISCONNECT,
            "username": username,
        }
        if reason:
            msg["reason"] = reason
        return msg
    
    @staticmethod
    def file_init(filename: str, filesize: int, filehash: str,
                  sender: str) -> Dict[str, Any]:
        """Create a file initialization message."""
        return {
            "type": MessageType.FILE_INIT,
            "filename": filename,
            "filesize": filesize,
            "filehash": filehash,
            "sender": sender,
        }
    
    @staticmethod
    def file_chunk(index: int, data_b64: str) -> Dict[str, Any]:
        """Create a file chunk message (data is base64-encoded)."""
        return {
            "type": MessageType.FILE_CHUNK,
            "index": index,
            "data": data_b64,
        }
    
    @staticmethod
    def file_complete(filename: str, total_chunks: int,
                      filehash: str) -> Dict[str, Any]:
        """Create a file completion message."""
        return {
            "type": MessageType.FILE_COMPLETE,
            "filename": filename,
            "total_chunks": total_chunks,
            "filehash": filehash,
        }
    
    @staticmethod
    def keep_alive(username: str) -> Dict[str, Any]:
        """Create a keep-alive message."""
        return {
            "type": MessageType.KEEP_ALIVE,
            "username": username,
            "timestamp": time.time(),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Serialization Helpers
# ─────────────────────────────────────────────────────────────────────────────

def encode_message(msg: Dict[str, Any]) -> bytes:
    """
    Encode a message dict to bytes with newline delimiter.
    
    Args:
        msg: Message dictionary
        
    Returns:
        UTF-8 encoded bytes ending with newline
    """
    return (json.dumps(msg) + "\n").encode("utf-8")


def decode_message(line: str) -> Optional[Dict[str, Any]]:
    """
    Decode a single line into a message dict.
    
    Args:
        line: A JSON string (without newline)
        
    Returns:
        Message dict, or None if invalid
    """
    line = line.strip()
    if not line:
        return None
    try:
        msg = json.loads(line)
        if not isinstance(msg, dict):
            return None
        if "type" not in msg:
            return None
        return msg
    except json.JSONDecodeError:
        return None


def is_valid_message(msg: Dict[str, Any]) -> bool:
    """Check if a message has a valid type."""
    if not isinstance(msg, dict):
        return False
    msg_type = msg.get("type")
    return msg_type in MessageType.all()


# ─────────────────────────────────────────────────────────────────────────────
# Message Buffer
# ─────────────────────────────────────────────────────────────────────────────

class MessageBuffer:
    """
    Thread-safe buffer for incoming TCP data.
    
    TCP is a stream protocol - messages may arrive:
    - Split across multiple recv() calls
    - Batched together in one recv() call
    
    This buffer accumulates bytes and extracts complete newline-delimited
    JSON messages.
    """
    
    def __init__(self):
        self._buffer = ""
        self._lock = threading.Lock()
    
    def add_data(self, data: bytes) -> None:
        """Add incoming bytes to the buffer."""
        with self._lock:
            self._buffer += data.decode("utf-8", errors="replace")
    
    def extract_messages(self) -> List[Dict[str, Any]]:
        """
        Extract all complete messages from buffer.
        
        Returns:
            List of parsed message dicts. Incomplete messages remain in buffer.
        """
        with self._lock:
            messages = []
            while "\n" in self._buffer:
                line, self._buffer = self._buffer.split("\n", 1)
                msg = decode_message(line)
                if msg is not None:
                    messages.append(msg)
            return messages
    
    def clear(self) -> None:
        """Clear the buffer."""
        with self._lock:
            self._buffer = ""
    
    @property
    def pending_bytes(self) -> int:
        """Number of bytes currently buffered."""
        with self._lock:
            return len(self._buffer)