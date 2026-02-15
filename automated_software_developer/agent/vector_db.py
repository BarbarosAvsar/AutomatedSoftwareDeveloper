"""Vector database adapter interfaces and local stubs."""

from __future__ import annotations

import logging
from collections.abc import Sequence

logger = logging.getLogger(__name__)


class VectorDBAdapter:
    """Base adapter interface for vector storage backends."""

    def upsert(self, namespace: str, ids: Sequence[str], vectors: Sequence[list[float]]) -> None:
        """Store vector embeddings for the given ids."""
        raise NotImplementedError

    def query(self, namespace: str, vector: list[float], top_k: int = 5) -> list[str]:
        """Return top-k nearest ids for a query vector."""
        raise NotImplementedError


class FaissAdapter(VectorDBAdapter):
    """Local FAISS-like stub that logs calls without external dependencies."""

    def upsert(self, namespace: str, ids: Sequence[str], vectors: Sequence[list[float]]) -> None:
        """Log upsert activity for the namespace."""
        logger.info(
            "FaissAdapter.upsert namespace=%s entries=%s dims=%s",
            namespace,
            len(ids),
            len(vectors[0]) if vectors else 0,
        )

    def query(self, namespace: str, vector: list[float], top_k: int = 5) -> list[str]:
        """Log query activity and return an empty result set in stub mode."""
        logger.info(
            "FaissAdapter.query namespace=%s top_k=%s dims=%s",
            namespace,
            top_k,
            len(vector),
        )
        return []
