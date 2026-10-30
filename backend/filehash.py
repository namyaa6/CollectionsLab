"""Line-ending-proof file hashing for run identity."""
import hashlib
from pathlib import Path


def normalize_newlines(raw: bytes) -> bytes:
    """CRLF (and lone CR) -> LF, so a Windows checkout hashes like the LF original."""
    return raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def sha256_normalized(raw: bytes) -> str:
    return hashlib.sha256(normalize_newlines(raw)).hexdigest()


def file_hash(path: Path) -> str:
    return sha256_normalized(path.read_bytes())
