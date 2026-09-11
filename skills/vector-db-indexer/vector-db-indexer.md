---
id: vector-db-indexer
name: vector-db-indexer
category: uncategorized
tags: []
author: opencode-core
version: 1.0.0
description:
---

---
id: vector-db-indexer
file_path: skills/vector-db-indexer.md
name: Vector DB Indexer
category: database
tags: [embeddings, vector-database, rag, chunking, qdrant]
author: opencode-core
version: 1.0.0
description: Chunk documents and store vector embeddings into a Vector DB.
---

# Vector DB Indexer

## Prerequisites & Dependencies
- Python 3.10+
- Packages: `pip install qdrant-client sentence-transformers tiktoken` (swap in `openai` for API embeddings; Chroma/pgvector equivalents follow the same flow)
- Environment: `EMBEDDING_MODEL` (e.g., `sentence-transformers/all-MiniLM-L6-v2`); `QDRANT_URL` and `QDRANT_API_KEY` when using managed Qdrant Cloud

## Execution Steps
1. Load source documents and normalize text: strip headers/footers, collapse whitespace, and extract metadata (source path, section title, timestamp).
2. Chunk with a token-bounded splitter (256-512 tokens) and 10-15% overlap so boundary context is preserved.
3. Generate embeddings in batches; ensure query-time embedding uses the exact same model and version.
4. Create the collection with matching vector size and distance metric (cosine for normalized embeddings) and add a payload index for metadata filtering.
5. Upsert points with deterministic UUIDs (hash of source path + chunk index) for idempotent re-indexing, storing chunk text and metadata as payload.
6. Verify: run semantic test queries, inspect top-k hits for relevance, and compare collection point count against expected chunk count.

```python
import hashlib, uuid
from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer

CHUNK, OVERLAP = 400, 60  # words; tune to your embedding model
model = SentenceTransformer("all-MiniLM-L6-v2")
client = QdrantClient(url="http://localhost:6333")
client.create_collection(
    "docs",
    vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE),
)

def chunk_text(text: str) -> list[str]:
    words = text.split()
    return [" ".join(words[i:i + CHUNK]) for i in range(0, len(words), CHUNK - OVERLAP)]

points = []
for doc in documents:  # [{"path": str, "text": str}]
    for i, chunk in enumerate(chunk_text(doc["text"])):
        pid = uuid.UUID(hashlib.md5(f"{doc['path']}:{i}".encode()).hexdigest())
        points.append(models.PointStruct(
            id=str(pid),
            vector=model.encode(chunk).tolist(),
            payload={"text": chunk, "source": doc["path"], "chunk": i},
        ))
client.upsert("docs", points=points, wait=True)
```
