"""EmbeddingProvider abstraction — same interface+Mock pattern as every
other domain in this codebase. Unlike most "mock" defaults here (which
serve fixed or synthetic-but-plausible fake data), HashingEmbeddingProvider
is a real algorithm run over real ingested text (feature hashing / the
"hashing trick" — a genuine classical information-retrieval technique,
not random noise): it is weaker than a dense neural embedding at capturing
synonyms and semantics, but it is not fake. OllamaEmbeddingProvider is the
real upgrade: genuine dense embeddings from a locally running Ollama
instance (`ollama pull nomic-embed-text` first — this is a distinct
embedding model from the chat model OLLAMA_MODEL points at, and Ollama
has no bundled default for it).
"""

import hashlib
import math
import re
from abc import ABC, abstractmethod

import httpx

_TOKEN_RE = re.compile(r"[a-z0-9]+")

_HASHING_DIMS = 256


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class EmbeddingProvider(ABC):
    name: str
    dims: int

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        raise NotImplementedError


class HashingEmbeddingProvider(EmbeddingProvider):
    """Feature-hashing bag-of-words: each token hashes into one of `dims`
    buckets, bucket counts are L2-normalized. Deterministic, zero external
    dependency, the checked-in default. Real cosine similarity between two
    hashed vectors reflects real shared vocabulary — it just has no notion
    of synonyms (e.g. "hike" vs "increase" score no higher than any other
    unrelated word pair), unlike a dense neural embedding."""

    name = "hashing"
    dims = _HASHING_DIMS

    async def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dims
        for token in _tokenize(text):
            bucket = int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16) % self.dims
            vector[bucket] += 1.0
        norm = math.sqrt(sum(v * v for v in vector))
        if norm == 0.0:
            return vector
        return [v / norm for v in vector]


class OllamaEmbeddingProvider(EmbeddingProvider):
    """Real dense embeddings via a locally running Ollama instance. Raises
    (rather than silently falling back to the hashing provider) if Ollama
    or the embedding model isn't reachable — the same "fail loudly, don't
    fake it" discipline as OllamaModelProvider (domains/ai/ollama_provider.py)."""

    name = "ollama"
    dims = 768  # nomic-embed-text's real output dimensionality

    def __init__(self, base_url: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def embed(self, text: str) -> list[float]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/api/embeddings", json={"model": self.model, "prompt": text}
            )
            response.raise_for_status()
        data = response.json()
        embedding = data.get("embedding")
        if not embedding:
            raise RuntimeError(f"Ollama returned no embedding for model {self.model!r}")
        return embedding


def get_embedding_provider() -> EmbeddingProvider:
    from app.core.config import get_settings

    settings = get_settings()
    if settings.embedding_provider == "hashing":
        return HashingEmbeddingProvider()
    if settings.embedding_provider == "ollama":
        return OllamaEmbeddingProvider(base_url=settings.ollama_base_url, model=settings.embedding_ollama_model)
    raise ValueError(f"Unknown EMBEDDING_PROVIDER: {settings.embedding_provider!r}")
