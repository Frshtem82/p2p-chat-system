"""
File transfer utilities.

Handles hashing, chunking, and formatting for file transfer.
"""

import os
import hashlib
import base64
from typing import Iterator, Tuple

from .constants import CHUNK_SIZE, FILE_HASH_ALGORITHM


class FileTransfer:
    """Static utilities for file transfer operations."""
    
    @staticmethod
    def calculate_hash(filepath: str, chunk_size: int = CHUNK_SIZE) -> str:
        """
        Calculate the hash of a file.
        
        Args:
            filepath: Path to the file
            chunk_size: Read chunk size (default 8KB)
            
        Returns:
            Hex digest of the hash
        """
        hasher = hashlib.new(FILE_HASH_ALGORITHM)
        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                hasher.update(chunk)
        return hasher.hexdigest()
    
    @staticmethod
    def get_file_size(filepath: str) -> int:
        """Get file size in bytes."""
        return os.path.getsize(filepath)
    
    @staticmethod
    def format_size(size_bytes: float) -> str:
        """
        Format bytes as human-readable string.
        
        Examples:
            1024      -> "1.00 KB"
            1048576   -> "1.00 MB"
        """
        if size_bytes < 0:
            return "0 B"
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size_bytes < 1024:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.2f} PB"
    
    @staticmethod
    def iter_chunks(filepath: str, chunk_size: int = CHUNK_SIZE
                    ) -> Iterator[Tuple[int, bytes]]:
        """
        Iterate over file chunks.
        
        Args:
            filepath: Path to the file
            chunk_size: Size of each chunk
            
        Yields:
            Tuples of (index, chunk_bytes)
        """
        index = 0
        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                yield index, chunk
                index += 1
    
    @staticmethod
    def encode_chunk(chunk: bytes) -> str:
        """Base64-encode a chunk for JSON compatibility."""
        return base64.b64encode(chunk).decode("ascii")
    
    @staticmethod
    def decode_chunk(encoded: str) -> bytes:
        """Decode a base64-encoded chunk."""
        return base64.b64decode(encoded)
    
    @staticmethod
    def get_unique_path(directory: str, filename: str) -> str:
        """
        Get a unique file path, avoiding overwriting.
        
        If 'report.pdf' exists, returns 'report_1.pdf', 'report_2.pdf', etc.
        
        Args:
            directory: Target directory
            filename: Desired filename
            
        Returns:
            Full path that doesn't exist yet
        """
        base, ext = os.path.splitext(filename)
        candidate = os.path.join(directory, filename)
        
        counter = 1
        while os.path.exists(candidate):
            candidate = os.path.join(directory, f"{base}_{counter}{ext}")
            counter += 1
        
        return candidate
    
    @staticmethod
    def validate_file(filepath: str) -> Tuple[bool, str]:
        """
        Validate that a file exists and is readable.
        
        Returns:
            (is_valid, error_message)
        """
        if not filepath:
            return False, "No file path provided"
        if not os.path.exists(filepath):
            return False, f"File not found: {filepath}"
        if not os.path.isfile(filepath):
            return False, f"Not a regular file: {filepath}"
        if not os.access(filepath, os.R_OK):
            return False, f"Permission denied: {filepath}"
        return True, ""