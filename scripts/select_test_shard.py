"""Select deterministic pytest file shards."""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: select_test_shard.py <shard_index> <shard_total>")
    shard_index = int(sys.argv[1])
    shard_total = int(sys.argv[2])
    if shard_total <= 0 or not 0 <= shard_index < shard_total:
        raise SystemExit("Invalid shard values")

    test_files = sorted(Path("tests").glob("test_*.py"))
    selected = [str(path) for i, path in enumerate(test_files) if i % shard_total == shard_index]
    if not selected:
        raise SystemExit("No tests selected for shard")
    print(" ".join(selected))


if __name__ == "__main__":
    main()
