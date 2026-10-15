"""Baseline semantic cache. Deliberately vulnerable, on purpose.

Two layers:

- exact match on prompt_hash (Redis, or memory fallback)
- semantic search on the MiniLM embedding (Qdrant, or memory fallback)

The verdict is stored in every payload from day one, but nothing reads it
yet. That is the point: Week 3 is the vulnerable baseline, Phase 3 turns the
same payload into a filtered search with one flag flip.

Pipeline order matters for the finding:

- cache_first (default, what real products do): lookup runs before screening.
  A hit returns with screening_ran=False. That is the hole Week 4 measures.
- screen_first: screening runs first, then lookup. Safe order, kept as the
  comparison arm.
"""

from __future__ import annotations

import hashlib
import math
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.verdict import classify_intent

EMBED_MODEL = "all-MiniLM-L6-v2"
EMBED_DIM = 384

_WORD_RE = re.compile(r"[a-z0-9]+")


def cosine_similarity(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right))
    norm_l = math.sqrt(sum(a * a for a in left))
    norm_r = math.sqrt(sum(b * b for b in right))
    if norm_l == 0 or norm_r == 0:
        return 0.0
    return dot / (norm_l * norm_r)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class StubEmbedder:
    """Deterministic word-hash embedding. No models, no network.

    Surface edits share almost all words, so they score near 1.0.
    Unrelated prompts share almost no words, so they score near 0.
    Good enough to prove the pipeline; the real model replaces it.
    """

    model_id = "stub-hash-v0"
    dim = 64

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for word in _WORD_RE.findall(text.lower()):
            slot = int(hashlib.sha256(word.encode()).hexdigest(), 16) % self.dim
            vec[slot] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


class SentenceTransformerEmbedder:
    """The real MiniLM embedder. Loaded once, called per request."""

    def __init__(self, model_id: str = EMBED_MODEL):
        from sentence_transformers import SentenceTransformer  # lazy: keeps import light

        self.model = SentenceTransformer(model_id)
        self.model_id = model_id
        self.dim = EMBED_DIM

    def embed(self, text: str) -> list[float]:
        return [float(v) for v in self.model.encode(text, normalize_embeddings=True)]


def payload_matches(payload: dict | None, require: dict | None) -> bool:
    """True when a stored entry's safety label satisfies the requirement.

    require is None for the vulnerable baseline: any similar entry may be
    served. With the Phase 3 defence it holds the fields that must agree,
    for example {"is_injection": False, "intent": "informational"}.
    """
    if not require:
        return True
    payload = payload or {}
    return all(payload.get(k) == v for k, v in require.items())


@dataclass
class CacheEntry:
    entry_id: str
    vector: list[float]
    payload: dict


@dataclass
class LookupResult:
    hit: bool
    similarity: float
    matched_id: str | None
    payload: dict | None


class MemoryExactStore:
    def __init__(self):
        self.items: dict[str, CacheEntry] = {}

    def get(self, prompt_hash: str) -> CacheEntry | None:
        return self.items.get(prompt_hash)

    def put(self, entry: CacheEntry) -> None:
        self.items[entry.payload["prompt_hash"]] = entry

    def clear(self) -> int:
        count = len(self.items)
        self.items.clear()
        return count

    def __len__(self) -> int:
        return len(self.items)


class MemoryVectorStore:
    def __init__(self):
        self.entries: list[CacheEntry] = []

    def search(self, vector: list[float], threshold: float, require: dict | None = None) -> LookupResult:
        best: CacheEntry | None = None
        best_sim = -1.0
        for entry in self.entries:
            if not payload_matches(entry.payload, require):
                continue
            sim = cosine_similarity(vector, entry.vector)
            if sim > best_sim:
                best_sim = sim
                best = entry
        if best is not None and best_sim >= threshold:
            return LookupResult(True, round(float(best_sim), 4), best.entry_id, best.payload)
        return LookupResult(False, round(float(best_sim) if best else 0.0, 4), None, None)

    def upsert(self, entry: CacheEntry) -> None:
        # One entry per prompt_hash: replace on re-ask.
        self.entries = [e for e in self.entries if e.payload["prompt_hash"] != entry.payload["prompt_hash"]]
        self.entries.append(entry)

    def clear(self) -> int:
        count = len(self.entries)
        self.entries.clear()
        return count

    def __len__(self) -> int:
        return len(self.entries)


class RedisExactStore:
    """Exact layer on Redis. Falls back to memory if Redis is unreachable."""

    def __init__(self, url: str):
        import json

        import redis  # lazy

        self._json = json
        self.client = redis.Redis.from_url(url, socket_connect_timeout=2)
        self.client.ping()
        self.memory = MemoryExactStore()
        self.backend = "redis"

    def get(self, prompt_hash: str) -> CacheEntry | None:
        raw = self.client.get(f"sentrygate:exact:{prompt_hash}")
        if raw is None:
            return self.memory.get(prompt_hash)
        data = self._json.loads(raw)
        return CacheEntry(entry_id=data["entry_id"], vector=data["vector"], payload=data["payload"])

    def put(self, entry: CacheEntry) -> None:
        self.memory.put(entry)
        self.client.set(
            f"sentrygate:exact:{entry.payload['prompt_hash']}",
            self._json.dumps({"entry_id": entry.entry_id, "vector": entry.vector, "payload": entry.payload}),
        )

    def clear(self) -> int:
        count = len(self.memory)
        self.memory.clear()
        for key in self.client.scan_iter("sentrygate:exact:*"):
            self.client.delete(key)
            count += 1
        return count


class QdrantVectorStore:
    """Semantic layer on Qdrant. Collection is bootstrapped on startup."""

    def __init__(self, url: str, collection: str = "sentrygate_cache", dim: int = EMBED_DIM):
        from qdrant_client import QdrantClient  # lazy
        from qdrant_client.http.models import Distance, VectorParams

        self.client = QdrantClient(url=url, timeout=5)
        self.collection = collection
        self.dim = dim
        if not self.client.collection_exists(collection):
            self.client.create_collection(
                collection_name=collection,
                vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
            )
        # Index the label fields the defence filters on, so the filter runs
        # inside the vector search rather than after it.
        from qdrant_client.http.models import PayloadSchemaType
        indexes = (("is_injection", PayloadSchemaType.BOOL), ("label_intent", PayloadSchemaType.KEYWORD))
        for field_name, schema in indexes:
            try:
                self.client.create_payload_index(self.collection, field_name=field_name, field_schema=schema)
            except Exception:
                pass  # already indexed
        self.backend = "qdrant"

    def search(self, vector: list[float], threshold: float, require: dict | None = None) -> LookupResult:
        query_filter = None
        if require:
            from qdrant_client.http.models import FieldCondition, Filter, MatchValue

            query_filter = Filter(must=[FieldCondition(key=k, match=MatchValue(value=v)) for k, v in require.items()])
        points = self.client.query_points(
            collection_name=self.collection, query=vector, query_filter=query_filter, limit=1, with_payload=True
        ).points
        if not points:
            return LookupResult(False, 0.0, None, None)
        top = points[0]
        if top.score >= threshold:
            payload = dict(top.payload or {})
            return LookupResult(True, round(float(top.score), 4), str(top.id), payload)
        return LookupResult(False, round(float(top.score), 4), None, None)

    def upsert(self, entry: CacheEntry) -> None:
        import uuid

        from qdrant_client.http.models import PointStruct

        point_id = entry.entry_id if _is_uuid(entry.entry_id) else uuid.uuid4().hex
        entry.entry_id = point_id
        self.client.upsert(
            collection_name=self.collection,
            points=[PointStruct(id=point_id, vector=entry.vector, payload=entry.payload)],
        )

    def clear(self) -> int:
        from qdrant_client.http.models import Filter

        # Delete-all needs a filter; empty filter matches everything.
        self.client.delete(collection_name=self.collection, points_selector=Filter(must=[]))
        return 0


def _is_uuid(value: str) -> bool:
    import re as _re

    return bool(_re.fullmatch(r"[0-9a-fA-F-]{32,36}", value))


@dataclass
class SemanticCache:
    """Exact first (free), then semantic (threshold). No verdict filter yet."""

    embedder: object
    exact: object
    vector: object
    threshold: float
    embed_model: str = EMBED_MODEL
    stats: dict = field(default_factory=lambda: {"hits": 0, "misses": 0, "upserts": 0})

    def lookup_with_vector(
        self, prompt_hash: str, vector: list[float],
        require: dict | None = None, threshold: float | None = None,
    ) -> LookupResult:
        """Exact match first, then similarity search.

        require and threshold come from the request: None means the baseline
        (any similar entry, global threshold). The defence passes the safety
        label the stored entry must carry, and a stricter threshold for risky
        kinds of question.
        """
        exact_hit = self.exact.get(prompt_hash)  # type: ignore[attr-defined]
        if exact_hit is not None and payload_matches(exact_hit.payload, require):
            self.stats["hits"] += 1
            return LookupResult(True, 1.0, exact_hit.entry_id, exact_hit.payload)
        limit = self.threshold if threshold is None else threshold
        result = self.vector.search(vector, limit, require)  # type: ignore[attr-defined]
        if result.hit:
            self.stats["hits"] += 1
        else:
            self.stats["misses"] += 1
        return result

    def lookup(self, prompt: str, prompt_hash: str) -> tuple[LookupResult, list[float]]:
        vector = self.embedder.embed(prompt)  # type: ignore[attr-defined]
        return self.lookup_with_vector(prompt_hash, vector), vector

    def store(
        self,
        prompt: str,
        prompt_hash: str,
        response: str,
        model: str,
        verdict: dict | None,
        vector: list[float] | None = None,
    ) -> str:
        import uuid

        vec = vector if vector is not None else self.embedder.embed(prompt)  # type: ignore[attr-defined]
        verdict = verdict or {}
        payload = {
            "prompt_text": prompt,
            "prompt_hash": prompt_hash,
            "response": response,
            "model": model,
            "is_injection": bool(verdict.get("is_injection", False)),
            "has_pii": bool(verdict.get("has_pii", False)),
            "intent": str(verdict.get("intent", "other")),
            # The same cheap keyword label an incoming question gets before the
            # cache is checked. The defence matches on this, not on "intent",
            # because "intent" also uses the personal-data scan, which an
            # incoming question has not had yet; matching across the two rules
            # would turn honest repeats into misses.
            "label_intent": classify_intent(prompt),
            "risk_level": str(verdict.get("risk_level", "low")),
            "injection_score": float(verdict.get("injection_score", 0.0)),
            "embed_model": self.embed_model,
            "created_at": _now_iso(),
        }
        entry = CacheEntry(entry_id=uuid.uuid4().hex, vector=list(vec), payload=payload)
        self.exact.put(entry)  # type: ignore[attr-defined]
        self.vector.upsert(entry)  # type: ignore[attr-defined]
        self.stats["upserts"] += 1
        return entry.entry_id

    def clear(self) -> int:
        left = self.exact.clear()  # type: ignore[attr-defined]
        right = self.vector.clear()  # type: ignore[attr-defined]
        return max(int(left), int(right))

    def size(self) -> int:
        try:
            return len(self.exact)  # type: ignore[arg-type]
        except TypeError:
            return 0


def build_embedder(settings, embedder=None):
    """Process-wide embedder. Stub in tests, real model when asked."""
    mode = getattr(settings, "cache_embedder", "auto")
    model_id = getattr(settings, "embed_model", EMBED_MODEL)
    started = time.perf_counter()
    if embedder is not None:
        return embedder, {"mode": "injected", "model": model_id, "load_ms": 0.0}
    if mode == "stub":
        stub = StubEmbedder()
        return stub, {"mode": "stub", "model": stub.model_id, "dim": stub.dim, "load_ms": 0.0}
    try:
        real = SentenceTransformerEmbedder(model_id)
        load_ms = round((time.perf_counter() - started) * 1000, 2)
        return real, {"mode": "sentence-transformers", "model": model_id, "dim": real.dim, "load_ms": load_ms}
    except Exception as exc:
        if mode == "hf":
            raise RuntimeError(f"CACHE_EMBEDDER=hf but embedder failed to load: {exc}") from exc
        stub = StubEmbedder()
        return stub, {
            "mode": "stub-fallback",
            "model": stub.model_id,
            "dim": stub.dim,
            "load_ms": round((time.perf_counter() - started) * 1000, 2),
            "fallback_reason": f"{type(exc).__name__}: {str(exc)[:160]}",
        }


def build_cache(settings, embedder=None, exact=None, vector=None) -> tuple[SemanticCache, dict]:
    """Process-wide cache. Memory fallback keeps the gateway running with no infra."""
    embed, embed_info = build_embedder(settings, embedder)
    backend = getattr(settings, "cache_backend", "auto")
    info: dict = {"embedder": embed_info, "threshold": settings.sim_threshold}

    exact_store = exact
    vector_store = vector
    if exact_store is None or vector_store is None:
        if backend == "memory":
            exact_store = exact_store or MemoryExactStore()
            vector_store = vector_store or MemoryVectorStore()
            info["backend"] = "memory"
        else:
            try:
                exact_store = exact_store or RedisExactStore(settings.redis_url)
                vector_store = vector_store or QdrantVectorStore(
                    settings.qdrant_url, dim=getattr(embed, "dim", EMBED_DIM)
                )
                info["backend"] = "redis+qdrant"
            except Exception as exc:
                exact_store = MemoryExactStore()
                vector_store = MemoryVectorStore()
                info["backend"] = "memory-fallback"
                info["fallback_reason"] = f"{type(exc).__name__}: {str(exc)[:160]}"

    cache = SemanticCache(
        embedder=embed,
        exact=exact_store,
        vector=vector_store,
        threshold=settings.sim_threshold,
        embed_model=getattr(settings, "embed_model", EMBED_MODEL),
    )
    info["size"] = cache.size()
    return cache, info
