"""Embed prompt journal entries into a local vectorstore stub."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

VECTOR_DIMENSIONS = 8


def _vector(seed: int) -> list[float]:
    output: list[float] = []
    for idx in range(VECTOR_DIMENSIONS):
        digest = hashlib.sha256(f"{seed}:{idx}".encode()).digest()
        value = int.from_bytes(digest[:4], "big") / 2**32
        output.append(round((value * 2.0) - 1.0, 6))
    return output


def main() -> None:
    """Read journal entries and write deterministic synthetic embeddings."""
    journal_path = Path(".autosd/prompt_journal.jsonl")
    output_dir = Path("data/vectorstore")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "journal_vectors.json"

    vectors: list[dict[str, object]] = []
    if journal_path.exists():
        for index, line in enumerate(journal_path.read_text(encoding="utf-8").splitlines()):
            if not line.strip():
                continue
            payload = json.loads(line)
            vectors.append(
                {
                    "id": str(payload.get("story_id", f"entry-{index}")),
                    "vector": _vector(index),
                }
            )

    output_path.write_text(json.dumps({"vectors": vectors}, indent=2), encoding="utf-8")
    print(f"Wrote {len(vectors)} vectors to {output_path}")


if __name__ == "__main__":
    main()
