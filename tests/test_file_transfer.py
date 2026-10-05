"""
Tests for file transfer utilities.

Covers:
- SHA256 hashing
- Size formatting
- Chunk iteration
- Base64 encode/decode
- Unique path generation
- File validation
"""

import os
import pytest
from shared.file_transfer import FileTransfer


# ─────────────────────────────────────────────────────────────────────────────
# Hash
# ─────────────────────────────────────────────────────────────────────────────

class TestHash:
    
    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_bytes(b"")
        h = FileTransfer.calculate_hash(str(f))
        # SHA256 of empty = e3b0c44298fc1c149afbf4c8996fb924...
        assert h.startswith("e3b0c442")
        assert len(h) == 64
    
    def test_known_content(self, tmp_path):
        f = tmp_path / "hello.txt"
        f.write_bytes(b"hello")
        h = FileTransfer.calculate_hash(str(f))
        # SHA256("hello") = 2cf24dba5fb0a30e26e83b2ac5b9e29e...
        assert h.startswith("2cf24dba")
    
    def test_same_content_same_hash(self, tmp_path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_bytes(b"same content")
        f2.write_bytes(b"same content")
        assert FileTransfer.calculate_hash(str(f1)) == \
               FileTransfer.calculate_hash(str(f2))
    
    def test_different_content_different_hash(self, tmp_path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_bytes(b"content A")
        f2.write_bytes(b"content B")
        assert FileTransfer.calculate_hash(str(f1)) != \
               FileTransfer.calculate_hash(str(f2))


# ─────────────────────────────────────────────────────────────────────────────
# Format Size
# ─────────────────────────────────────────────────────────────────────────────

class TestFormatSize:
    
    def test_bytes(self):
        assert FileTransfer.format_size(0) == "0.00 B"
        assert FileTransfer.format_size(1) == "1.00 B"
        assert FileTransfer.format_size(512) == "512.00 B"
    
    def test_kilobytes(self):
        assert FileTransfer.format_size(1024) == "1.00 KB"
        assert FileTransfer.format_size(1536) == "1.50 KB"
    
    def test_megabytes(self):
        assert FileTransfer.format_size(1024 * 1024) == "1.00 MB"
        assert FileTransfer.format_size(2_500_000) == "2.38 MB"
    
    def test_gigabytes(self):
        assert FileTransfer.format_size(1024 ** 3) == "1.00 GB"
    
    def test_negative(self):
        # Should not crash
        assert FileTransfer.format_size(-1) == "0 B"


# ─────────────────────────────────────────────────────────────────────────────
# Chunks
# ─────────────────────────────────────────────────────────────────────────────

class TestChunks:
    
    def test_iter_chunks(self, tmp_path):
        f = tmp_path / "data.bin"
        f.write_bytes(b"A" * (8192 * 3 + 100))  # 3 full chunks + partial
        chunks = list(FileTransfer.iter_chunks(str(f)))
        assert len(chunks) == 4
        assert all(len(c[1]) <= 8192 for c in chunks)
        # First 3 chunks should be full
        assert len(chunks[0][1]) == 8192
        assert len(chunks[1][1]) == 8192
        assert len(chunks[2][1]) == 8192
        assert len(chunks[3][1]) == 100
    
    def test_iter_chunks_empty(self, tmp_path):
        f = tmp_path / "empty.bin"
        f.write_bytes(b"")
        chunks = list(FileTransfer.iter_chunks(str(f)))
        assert chunks == []
    
    def test_chunk_indices(self, tmp_path):
        f = tmp_path / "data.bin"
        f.write_bytes(b"X" * (8192 * 3))
        chunks = list(FileTransfer.iter_chunks(str(f)))
        indices = [c[0] for c in chunks]
        assert indices == [0, 1, 2]


# ─────────────────────────────────────────────────────────────────────────────
# Base64
# ─────────────────────────────────────────────────────────────────────────────

class TestBase64:
    
    def test_roundtrip(self):
        for data in [b"", b"hello", b"\x00\x01\x02\xff", os.urandom(1024)]:
            encoded = FileTransfer.encode_chunk(data)
            decoded = FileTransfer.decode_chunk(encoded)
            assert decoded == data
    
    def test_encoded_is_string(self):
        encoded = FileTransfer.encode_chunk(b"test")
        assert isinstance(encoded, str)


# ─────────────────────────────────────────────────────────────────────────────
# Unique Path
# ─────────────────────────────────────────────────────────────────────────────

class TestUniquePath:
    
    def test_no_conflict(self, tmp_path):
        path = FileTransfer.get_unique_path(str(tmp_path), "file.txt")
        assert path == str(tmp_path / "file.txt")
    
    def test_one_conflict(self, tmp_path):
        (tmp_path / "file.txt").write_text("existing")
        path = FileTransfer.get_unique_path(str(tmp_path), "file.txt")
        assert path == str(tmp_path / "file_1.txt")
    
    def test_multiple_conflicts(self, tmp_path):
        (tmp_path / "file.txt").write_text("a")
        (tmp_path / "file_1.txt").write_text("b")
        (tmp_path / "file_2.txt").write_text("c")
        path = FileTransfer.get_unique_path(str(tmp_path), "file.txt")
        assert path == str(tmp_path / "file_3.txt")
    
    def test_with_extension(self, tmp_path):
        (tmp_path / "photo.jpg").write_text("x")
        path = FileTransfer.get_unique_path(str(tmp_path), "photo.jpg")
        assert path.endswith("photo_1.jpg")


# ─────────────────────────────────────────────────────────────────────────────
# Validate
# ─────────────────────────────────────────────────────────────────────────────

class TestValidate:
    
    def test_valid_file(self, tmp_path):
        f = tmp_path / "ok.txt"
        f.write_text("ok")
        ok, err = FileTransfer.validate_file(str(f))
        assert ok
        assert err == ""
    
    def test_empty_path(self):
        ok, err = FileTransfer.validate_file("")
        assert not ok
        assert "No file" in err
    
    def test_nonexistent(self, tmp_path):
        ok, err = FileTransfer.validate_file(str(tmp_path / "ghost"))
        assert not ok
        assert "not found" in err.lower()
    
    def test_directory(self, tmp_path):
        ok, err = FileTransfer.validate_file(str(tmp_path))
        assert not ok
        assert "regular file" in err.lower()