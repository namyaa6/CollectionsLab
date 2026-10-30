"""Disk cache for LLM responses, plus a tiny CLI: python -m backend.llm.cache --clear"""
import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_DIR = Path(__file__).resolve().parents[2] / "data" / "cache"


def make_key(payload: dict) -> str:
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class DiskCache:
    """One JSON file per key. Corrupt files count as a miss."""

    def __init__(self, directory: Path = DEFAULT_DIR):
        self.dir = Path(directory)

    def get(self, key: str) -> Optional[dict]:
        try:
            return json.loads((self.dir / f"{key}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def put(self, key: str, entry: dict) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self.dir / f"{key}.json.tmp"
        tmp.write_text(json.dumps(entry), encoding="utf-8")
        os.replace(tmp, self.dir / f"{key}.json")  # atomic: no half-written entries

    def clear(self) -> int:
        files = list(self.dir.glob("*.json")) if self.dir.exists() else []
        for f in files:
            f.unlink()
        return len(files)

    def count(self) -> int:
        return len(list(self.dir.glob("*.json"))) if self.dir.exists() else 0


def main(argv: Optional[list[str]] = None, cache: Optional[DiskCache] = None) -> None:
    parser = argparse.ArgumentParser(description="Manage the LLM disk cache.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--clear", action="store_true", help="delete all cached responses")
    group.add_argument("--stats", action="store_true", help="show number of cached responses")
    args = parser.parse_args(argv)
    cache = cache or DiskCache()
    if args.clear:
        print(f"Deleted {cache.clear()} cached responses from {cache.dir}")
    else:
        print(f"{cache.count()} cached responses in {cache.dir}")


if __name__ == "__main__":
    main()
