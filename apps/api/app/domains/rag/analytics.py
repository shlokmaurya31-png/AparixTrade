"""Pure vector math for RAG retrieval — no ANN index (FAISS/pgvector/etc):
the current corpus (ingested news articles) is tens, not millions, of rows,
so a full-scan cosine-similarity ranking is genuinely correct at this data
volume, not a shortcut. See domains/admin/data_quality.py's
check_candle_integrity() docstring for the same kind of documented,
volume-scoped limitation elsewhere in this codebase — an ANN index would
be real future work before a much larger corpus makes a full scan slow.
"""

import math


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise ValueError(f"Vector dimension mismatch: {len(a)} vs {len(b)}")
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def rank_by_similarity(query_vector: list[float], candidates: list[tuple[str, list[float]]], top_k: int) -> list[tuple[str, float]]:
    """candidates: list of (id, vector). Returns the top_k ids by cosine
    similarity to query_vector, highest first."""
    scored = [(cid, cosine_similarity(query_vector, vec)) for cid, vec in candidates]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:top_k]
