"""Singleton embedding service using sentence-transformers.

Gracefully degrades when dependencies are missing or disabled via config.
"""
from __future__ import annotations

import logging
from typing import Optional

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_model = None
_model_loaded = False


def _get_model():
    """Lazy-load the SentenceTransformer model. Returns None if disabled or unavailable."""
    global _model, _model_loaded
    if _model_loaded:
        return _model

    _model_loaded = True
    settings = get_settings()

    if not settings.embedding_enabled:
        logger.info("Embeddings disabled via config (EMBEDDING_ENABLED=false)")
        return None

    try:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(settings.embedding_model_name)
        logger.info("Loaded embedding model: %s", settings.embedding_model_name)
    except Exception as e:
        logger.warning("Failed to load embedding model: %s", e)
        _model = None

    return _model


def embed_product_text(
    department: Optional[str],
    subcategory: Optional[str],
    brand: Optional[str],
    name: str,
) -> str:
    """Build the text to embed by concatenating non-null product fields."""
    parts = [p for p in (department, subcategory, brand, name) if p]
    return " ".join(parts)


def embed_texts(texts: list[str]) -> Optional[list[list[float]]]:
    """Batch-encode texts into embeddings. Returns None on failure or if disabled."""
    model = _get_model()
    if model is None:
        return None

    try:
        embeddings = model.encode(texts, normalize_embeddings=True)
        return [emb.tolist() for emb in embeddings]
    except Exception as e:
        logger.warning("embed_texts failed: %s", e)
        return None


__all__ = ["embed_product_text", "embed_texts"]
