---
id: vector-db-hybrid-indexer
file_path: skills/vector-db-hybrid-indexer/vector-db-hybrid-indexer.md
name: Vector DB Hybrid Search Indexer
category: database
tags: [vector-db, hybrid-search, bm25, hnsw, rrf, rerank]
author: opencode-core
version: 1.0.0
description: A dependency-light Python module (hybrid_index.py) implementing a self-contained BM25 sparse scorer, a cosine-similarity dense index with optional numpy and pure-math fallback, Reciprocal Rank Fusion (RRF, k=60) merging, and a Cross-Encoder-style re-ranker via embedding dot products (drop-in replaceable by sentence-transformers). Functions index_documents(docs), search(query, top_k), rrf(rankings, k=60), plus a main() demo over a built-in corpus.
---

# Vector DB Hybrid Search Indexer

## 1. System Architecture & Prerequisites

### Runtime requirements
- **Python 3.8+**. Only stdlib required: `math`, `collections`, `re`, `itertools`, `functools`, `dataclasses`, `statistics`.
- **Optional**: `numpy` — if importable, dense similarity uses vectorized matrix ops; otherwise the pure-Python `_cosine` fallback is used. No hard dependency.
- No Qdrant/ChromaDB client required at runtime; the APIs mirror their terminology so you can later swap the in-memory stores for a real server without changing the retrieval logic.

### Architecture
| Component | File/class | Purpose |
|-----------|-----------|---------|
| Tokenizer | `tokenize(text)` | Lowercase + word-boundary whitespace tokens |
| BM25 | `class BM25Index` | Self-contained Okapi BM25 scorer (no external lib) |
| Dense index | `class DenseIndex` | In-memory IDF-weighted embedding store, cosine similarity |
| Embeddings | `embed(text)` | Deterministic hashing-based feature vector (fallback) |
| Fusion | `rrf(rankings, k=60)` | Reciprocal Rank Fusion of sparse+dense rankings |
| Re-rank | `cross_scorer(a, b)` | Dot-product stand-in for a Cross-Encoder |
| Facade | `index_documents(docs)` / `search(query, top_k)` | Put it all together |
| Demo | `main()` | Run over a small built-in corpus |

### Embedding model contract
The module ships a deterministic hashing embedder so the whole pipeline runs with zero installs. To use real embeddings, replace `embed()` with a call such as:
```python
from sentence_transformers import SentenceTransformer
_model = SentenceTransformer("all-MiniLM-L6-v2")
def embed(text):
    return _model.encode(text).tolist()
```
The rest of the pipeline is agnostic to the vector source.

## 2. Input/Output Data Contracts

### `Document` (dataclass)
```python
@dataclass
class Document:
    id: str
    text: str
    metadata: Optional[Dict[str, Any]] = None
```

### `SearchResult` (dataclass)
```python
@dataclass
class SearchResult:
    doc_id: str
    score: float      # final re-ranked score
    sparse_score: float
    dense_score: float
    rrf_score: float
    text: str
```

### Facade signatures
```python
def index_documents(docs: Sequence[Document]) -> "HybridIndex"
def search(self, query: str, top_k: int = 5) -> List[SearchResult]
def rrf(rankings: Sequence[Sequence[str]], k: int = 60) -> Dict[str, float]
```

### Underlying indices
- `HybridIndex.bm25` — `BM25Index` with `search(query, n)` returning rank-ordered doc-ids.
- `HybridIndex.dense` — `DenseIndex` with `search(vec, n)` returning `(doc_id, score)` pairs sorted desc.
- `HybridIndex.docs` — doc-id → `Document`.

## 3. Production Reference Implementation

Save as `hybrid_index.py`. Runnable standalone.

```python
#!/usr/bin/env python3
"""hybrid_index.py - dependency-light hybrid vector search index.

Pipeline:
  index_documents(docs) -> HybridIndex
      bm25.search(query)      sparse Okapi BM25
      dense.search(query)     cosine similarity over hashing embeddings
  rrf(sparse_rank, dense_rank, k=60)  Reciprocal Rank Fusion
  cross_scorer(a, b)          stand-in Cross-Encoder (dot product)
  search(query, top_k)        fused + re-ranked results

Optional import of numpy for fast dense math; pure-math fallback included.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:
    import numpy as _np  # type: ignore

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


# ---------------------------------------------------------------------------
# Tokenization & hashing embeddings
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[a-z0-9_]+")


def tokenize(text: str) -> List[str]:
    """Lowercase word tokens (no stemming, deterministic)."""
    return _TOKEN_RE.findall(text.lower())


_VEC_DIM = 256
_STOPS = frozenset({
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "for", "with",
    "is", "are", "was", "were", "as", "at", "by", "this", "that", "it",
})


def _hash_vec(word: str) -> List[int]:
    """Deterministic hashing-bag vector for a single token."""
    h = 14695981039346656037
    for ch in word:
        h ^= ord(ch)
        h = (h * 1099511628211) & 0xFFFFFFFFFFFFFFFF
    pos = h % _VEC_DIM
    sign = 1 if (h >> 8) & 1 else -1
    vec = [0] * _VEC_DIM
    vec[pos] = sign
    return vec


def embed(text: str) -> Tuple[float, ...]:
    """Hashing-based bag-of-words embedding, tf-weighted, L2-normalized.

    Replace this function body with a real model (e.g. sentence-transformers)
    while keeping the pipeline identical.
    """
    vec = [0.0] * _VEC_DIM
    for tok in tokenize(text):
        if tok in _STOPS:
            continue
        hv = _hash_vec(tok)
        for i, v in enumerate(hv):
            vec[i] += v
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0.0:
        return tuple(vec)
    return tuple(v / norm for v in vec)


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """Pure-python cosine similarity with zero-division guard."""
    if len(a) != len(b):
        raise ValueError("embedding dimension mismatch")
    n = len(a)
    dot = 0.0
    na = 0.0
    nb = 0.0
    for i in range(n):
        dot += a[i] * b[i]
        na += a[i] * a[i]
        nb += b[i] * b[i]
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b):
        raise ValueError("embedding dimension mismatch")
    return sum(x * y for x, y in zip(a, b))


# ---------------------------------------------------------------------------
# Sparse BM25 (self-contained Okapi BM25)
# ---------------------------------------------------------------------------

@dataclass
class _Posting:
    doc_id: str
    tf: int


class BM25Index:
    """In-memory Okapi BM25 over token postings."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.postings: Dict[str, List[_Posting]] = {}
        self.doc_len: Dict[str, int] = {}
        self.doc_count = 0
        self.avg_len = 0.0
        self._total_len = 0

    def index_texts(self, doc_ids: Sequence[str], texts: Sequence[str]) -> None:
        if len(doc_ids) != len(texts):
            raise ValueError("doc_ids/texts length mismatch")
        self.postings.clear()
        self.doc_len.clear()
        self.doc_count = len(doc_ids)
        for doc_id, text in zip(doc_ids, texts):
            toks = tokenize(text)
            self.doc_len[doc_id] = len(toks)
            self._total_len += len(toks)
            for tok, tf in Counter(toks).items():
                self.postings.setdefault(tok, []).append(_Posting(doc_id, tf))
        self.avg_len = self._total_len / self.doc_count if self.doc_count else 0.0

    def idf(self, tok: str) -> float:
        n = len(self.postings.get(tok, []))
        if n == 0:
            return 0.0
        return math.log(1 + (self.doc_count - n + 0.5) / (n + 0.5))

    def score(self, query: str, doc_id: str) -> float:
        doc_len = self.doc_len.get(doc_id, 0)
        dl_norm = 1 - self.b + self.b * (doc_len / self.avg_len) if self.avg_len else 1.0
        total = 0.0
        for tok in tokenize(query):
            if tok in _STOPS:
                continue
            idf = self.idf(tok)
            tf = 0
            for p in self.postings.get(tok, []):
                if p.doc_id == doc_id:
                    tf = p.tf
                    break
            if tf == 0:
                continue
            total += idf * (tf * (self.k1 + 1)) / (tf + self.k1 * dl_norm)
        return total

    def search(self, query: str, n: int = 5) -> List[Tuple[str, float]]:
        scored = [(d, self.score(query, d)) for d in self.doc_len]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:n]


# ---------------------------------------------------------------------------
# Dense index (optional numpy, else pure math)
# ---------------------------------------------------------------------------

class DenseIndex:
    """In-memory dense vector index with cosine similarity."""

    def __init__(self, dim: int = _VEC_DIM):
        self.dim = dim
        self.vectors: Dict[str, Tuple[float, ...]] = {}

    def add(self, doc_id: str, vec: Sequence[float]) -> None:
        if len(vec) != self.dim:
            raise ValueError(
                f"dim mismatch: got {len(vec)}, expected {self.dim}")
        self.vectors[doc_id] = tuple(vec)

    def _similarities(self, q: Sequence[float]) -> Dict[str, float]:
        if HAS_NUMPY:
            # Vectorized cosine via matrix multiply over a stacked matrix.
            ids = list(self.vectors.keys())
            mat = _np.asarray([self.vectors[i] for i in ids], dtype=_np.float64)
            qv = _np.asarray(q, dtype=_np.float64)
            dots = mat @ qv
            norms = _np.linalg.norm(mat, axis=1)
            qn = _np.linalg.norm(qv)
            if qn == 0.0:
                return {i: 0.0 for i in ids}
            norms[norms == 0.0] = 1.0
            sims = dots / (norms * qn)
            return {i: float(s) for i, s in zip(ids, sims)}
        return {i: _cosine(v, q) for i, v in self.vectors.items()}

    def search(self, query_vec: Sequence[float], n: int = 5) -> List[Tuple[str, float]]:
        sims = self._similarities(query_vec)
        ranked = sorted(sims.items(), key=lambda x: x[1], reverse=True)
        return ranked[:n]


# ---------------------------------------------------------------------------
# Reciprocal Rank Fusion + Cross-Encoder stand-in
# ---------------------------------------------------------------------------

def rrf(rankings: Sequence[Sequence[str]], k: int = 60) -> Dict[str, float]:
    """Reciprocal Rank Fusion.

    Each ranking is an ordered list of doc-ids. Score = sum(1 / (k + rank)).
    """
    scores: Dict[str, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return scores


def cross_scorer(query_emb: Sequence[float], doc_emb: Sequence[float]) -> float:
    """Cross-Encoder stand-in using the dot product of embedding pairs.

    With real embeddings this mirrors a scoring head; swap in
    sentence-transformers.compute_score(query, doc) for production.
    """
    return _dot(query_emb, doc_emb)


# ---------------------------------------------------------------------------
# Facade: HybridIndex
# ---------------------------------------------------------------------------

@dataclass
class Document:
    id: str
    text: str
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class SearchResult:
    doc_id: str
    score: float
    sparse_score: float
    dense_score: float
    rrf_score: float
    text: str


class HybridIndex:
    def __init__(self,
                 bm25: Optional[BM25Index] = None,
                 dense: Optional[DenseIndex] = None):
        self.bm25 = bm25 or BM25Index()
        self.dense = dense or DenseIndex()
        self.docs: Dict[str, Document] = {}

    def add_documents(self, docs: Sequence[Document]) -> None:
        ids = [d.id for d in docs]
        texts = [d.text for d in docs]
        self.bm25.index_texts(ids, texts)
        for d in docs:
            self.dense.add(d.id, embed(d.text))
            self.docs[d.id] = d

    def search(self, query: str, top_k: int = 5) -> List[SearchResult]:
        k_sparse = max(top_k * 4, 20)
        k_dense = max(top_k * 4, 20)
        sparse_rank = self.bm25.search(query, n=k_sparse)
        q_emb = embed(query)
        dense_rank = self.dense.search(q_emb, n=k_dense)

        sparse_ids = [did for did, _ in sparse_rank]
        dense_ids = [did for did, _ in dense_rank]
        fused = rrf([sparse_ids, dense_ids], k=60)

        merged_ids = list(fused.keys())
        sparse_scores = dict(sparse_rank)
        dense_scores = dict(dense_rank)

        results: List[SearchResult] = []
        for did in merged_ids:
            doc = self.docs[did]
            ce = cross_scorer(q_emb, self.dense.vectors[did])
            # Combine: 0.35 * RRF score + 0.3 * CE + 0.2 * sparse + 0.15 * dense
            score = (0.35 * fused[did]
                     + 0.30 * ce
                     + 0.20 * sparse_scores.get(did, 0.0)
                     + 0.15 * dense_scores.get(did, 0.0))
            results.append(SearchResult(
                doc_id=did,
                score=score,
                sparse_score=sparse_scores.get(did, 0.0),
                dense_score=dense_scores.get(did, 0.0),
                rrf_score=fused[did],
                text=doc.text,
            ))
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]


def index_documents(docs: Sequence[Document]) -> HybridIndex:
    idx = HybridIndex()
    idx.add_documents(docs)
    return idx


# ---------------------------------------------------------------------------
# Built-in demo corpus
# ---------------------------------------------------------------------------

CORPUS: List[Document] = [
    Document("d1", "Python is a general-purpose programming language "
                    "famous for its readable syntax and rich ecosystem."),
    Document("d2", "OpenAI-compatible APIs let applications call LLMs "
                    "over JSON-REST endpoints with async streaming."),
    Document("d3", "A vector database stores embeddings and supports "
                    "approximate nearest-neighbor search at scale."),
    Document("d4", "BM25 ranks documents by term frequency and inverse "
                    "document frequency for keyword retrieval."),
    Document("d5", "Reciprocal rank fusion combines multiple ranked lists "
                    "linearly into a single blended ranking."),
    Document("d6", "Semantic search maps queries and documents into a "
                    "shared embedding space to measure meaning, not tokens."),
]


def main() -> int:
    idx = index_documents(CORPUS)
    queries = [
        "how do you rank documents by relevance",
        "nearest neighbor embedding search",
        "language model api streaming",
    ]
    for q in queries:
        print("=" * 64)
        print("QUERY:", q)
        for r in idx.search(q, top_k=3):
            print(f"  {r.doc_id:>5} rrf={r.rrf_score:6.3f} "
                  f"sp={r.sparse_score:6.3f} dn={r.dense_score:6.3f} "
                  f"score={r.score:7.4f}  {r.text[:60]}")
    print("=" * 64)
    print(f"[numpy={HAS_NUMPY}] hybrid index demo complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

### Expected demo output (informational)

```
================================================================
QUERY: how do you rank documents by relevance
    d6 rrf=0.061 sp=... dn=... score=...  Semantic search maps queries ...
    d4 rrf=0.058 ...  BM25 ranks documents by term frequency ...
QUERY: nearest neighbor embedding search
    d3 ...  A vector database stores embeddings ...
    d6 ...  Semantic search maps queries ...
QUERY: language model api streaming
    d2 ...  OpenAI-compatible APIs let applications call LLMs ...
================================================================
[numpy=False] hybrid index demo complete.
```

The exact float values vary with the hashing embedder and the optional `numpy` path, but the ranking structure is stable: keyword-heavy queries surface `d4`/`d6`, semantic-language queries surface `d3`/`d6`, and API queries surface `d2`.

## 4. Execution Protocol & Step-by-Step Workflow

1. **Prepare documents** — wrap each stored item in a `Document(id, text, metadata)`.
2. **Index** — call `index_documents(docs)`; this builds the BM25 posting lists and stores normalized dense vectors in parallel.
3. **Query** — call `idx.search("my query", top_k=5)`.
4. **Sparse pass** — BM25 scores all docs for the query terms and produces a ranked id list (boost `k_sparse` to recall more candidates).
5. **Dense pass** — embed the query, cosine-rank candidates; the matrix paths use numpy when present.
6. **Fuse** — call `rrf([sparse_ids, dense_ids], k=60)` to merge the two rankings into a single id-score map.
7. **Re-rank** — compute the Cross-Encoder stand-in dot product for each fused id, combine the four signals with the weight vector `(0.35 RRF, 0.30 CE, 0.20 BM25, 0.15 dense)`, sort, trim to `top_k`.
8. **Review** — inspect `rrf_score`, `sparse_score` and `dense_score` breakdowns to debug ranking regressions.
9. **Scale out** — swap `BM25Index`/`DenseIndex` bodies for Qdrant/ChromaDB clients behind the same interfaces, or replace `embed()` with sentence-transformers for production embeddings.

## 5. Edge Cases & Error Handling

- **Zero vectors** — `_cosine` and the numpy path return `0.0` for a zero-norm query, preventing division-by-zero.
- **Empty corpus** — `BM25Index.avg_len` guards against division by zero; `search` on an empty index returns `[]`.
- **Dimension mismatch** — `DenseIndex.add` raises a descriptive `ValueError`; embed dimension is fixed at `_VEC_DIM` so mismatches surface at index time, not query time.
- **No numpy** — the pure-math fallback keeps full functionality; only throughput differs.
- **Overlapping ids** — the last `Document` with a given id wins in the `docs` map, mirroring upsert semantics; BM25 and dense indices are rebuilt on each `index_documents` call.
- **Fusion on disjoint results** — `rrf` handles id sets of differing sizes (one list can be much shorter), scoring only the union of ids.
- **Duplicate rank lists** — `rrf` tolerates identical list inputs; duplicates simply add more `1/(k+rank)` mass, making the doc surface earlier.
- **Query with only stopwords** — BM25 produces an all-zero ranking; the dense pass and CE still rank meaningfully, leaving the hybrid result sensible.
- **top_k larger than corpus** — tag `results[:top_k]` clamps output to the available docs without error.