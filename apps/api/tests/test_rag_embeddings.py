import pytest

from app.domains.rag.analytics import cosine_similarity, rank_by_similarity
from app.domains.rag.embeddings import HashingEmbeddingProvider

# ── cosine_similarity (pure math, hand-verifiable) ──────────────────────


def test_cosine_similarity_of_identical_vectors_is_one():
    v = [1.0, 2.0, 3.0]
    assert cosine_similarity(v, v) == pytest.approx(1.0)


def test_cosine_similarity_of_orthogonal_vectors_is_zero():
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_similarity_of_opposite_vectors_is_negative_one():
    assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)


def test_cosine_similarity_of_zero_vector_is_zero_not_a_division_error():
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0


def test_cosine_similarity_rejects_mismatched_dimensions():
    with pytest.raises(ValueError):
        cosine_similarity([1.0, 2.0], [1.0, 2.0, 3.0])


def test_rank_by_similarity_orders_highest_first():
    query = [1.0, 0.0]
    candidates = [("low", [0.0, 1.0]), ("high", [1.0, 0.0]), ("mid", [1.0, 1.0])]
    ranked = rank_by_similarity(query, candidates, top_k=3)
    assert [cid for cid, _ in ranked] == ["high", "mid", "low"]


def test_rank_by_similarity_respects_top_k():
    query = [1.0, 0.0]
    candidates = [(str(i), [1.0, float(i)]) for i in range(10)]
    ranked = rank_by_similarity(query, candidates, top_k=2)
    assert len(ranked) == 2


# ── HashingEmbeddingProvider (real bag-of-words, not random noise) ──────


async def test_hashing_embedding_is_deterministic():
    provider = HashingEmbeddingProvider()
    a = await provider.embed("RBI hikes repo rate by 25 basis points")
    b = await provider.embed("RBI hikes repo rate by 25 basis points")
    assert a == b


async def test_hashing_embedding_is_unit_normalized():
    provider = HashingEmbeddingProvider()
    vector = await provider.embed("inflation cooled to 4.2 percent in August")
    norm_sq = sum(v * v for v in vector)
    assert norm_sq == pytest.approx(1.0, abs=1e-6)


async def test_hashing_embedding_of_empty_text_is_the_zero_vector_not_an_error():
    provider = HashingEmbeddingProvider()
    vector = await provider.embed("")
    assert vector == [0.0] * provider.dims


async def test_shared_vocabulary_scores_higher_than_unrelated_text():
    """The real signal a bag-of-words embedding can and can't capture: exact
    shared words score higher, synonyms/paraphrases don't (documented
    limitation vs. a dense neural embedding — see embeddings.py docstring)."""
    provider = HashingEmbeddingProvider()
    query = await provider.embed("RBI expands digital rupee pilot to more retail partners")
    related = await provider.embed("RBI expands digital rupee pilot with new participating banks")
    unrelated = await provider.embed("Monsoon rainfall exceeds seasonal average across southern states")

    score_related = cosine_similarity(query, related)
    score_unrelated = cosine_similarity(query, unrelated)
    assert score_related > score_unrelated
