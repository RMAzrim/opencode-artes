---
id: rag-chunking-evaluator
file_path: skills/rag-chunking-evaluator/rag-chunking-evaluator.md
name: RAG Chunking Evaluator
category: ai-ops
tags: [rag, chunking, embeddings, llm, pipelines]
author: opencode-core
version: 1.0.0
description: Analyze document structures to recommend optimal chunking strategies and overlap ratios for RAG pipelines.
---

# RAG Chunking Evaluator

## Prerequisites & Dependencies
- Python 3.10+ with `pip install langchain openai tiktoken`
- Access to an LLM API key (OpenAI, Anthropic, or similar) for generating test embeddings
- A sample document corpus (PDFs, txt files, web pages) to analyze
- Optional: `pip install mlflow` for experiment tracking

## Execution Steps
1. Load the document corpus and split into individual pages or sections
2. Tokenize each section using `tiktoken` with the target model's encoder (e.g., `gpt-4o` or `gpt-4-turbo`)
3. Experiment with chunking strategies:
   - **Fixed-size chunks**: constant token count (e.g., 256, 512, 1024 tokens)
   - **Recursive character splitting**: break on paragraphs, sentences, words with overlap
   - **Section-aware splitting**: respect headings, tables, and code blocks as natural boundaries
4. For each strategy, generate embeddings via the LLM API and index into a vector store (Chroma, Pinecone, Qdrant)
5. Retrieve test queries and measure retrieval metrics:
   - **Recall@k**: percentage of relevant documents found in top-k results
   - **Precision@k**: percentage of retrieved documents that are relevant
   - **Answer accuracy**: end-to-end QA correctness using the retrieved context
6. Tune overlap ratios (typically 10–25% of chunk size) to minimize information loss at boundaries
7. Document the optimal strategy and produce a config file (`chunk_size`, `overlap`, `splitter_type`) for production RAG pipelines

```python
# Example: Recursive chunking with tiktoken and overlap
import tiktoken
from langchain.text_splitter import RecursiveCharacterTextSplitter

enc = tiktoken.get_encoding("cl100k_base")  # gpt-4o encoding

def count_tokens(text):
    return len(enc.encode(text))

def chunk_documents(documents, chunk_size=512, chunk_overlap=60):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", " ", ""],
    )
    chunks = []
    for doc in documents:
        chunks.extend(splitter.split_text(doc))
    return chunks

documents = [
    """Artificial Intelligence (AI) refers to the simulation of human intelligence processes by computer systems. These processes include learning, reasoning, and self-correction. ...""",
    """Machine Learning (ML) is a subset of AI that focuses on the development of algorithms that allow computers to learn from data ...""",
]

chunks = chunk_documents(documents, chunk_size=300, chunk_overlap=50)
print(f"Total chunks generated: {len(chunks)}")
for i, c in enumerate(chunks[:3]):
    print(f"Chunk {i}: {count_tokens(c)} tokens – {c[:60]}...")
```

```bash
pip install langchain openai tiktoken
python rag_chunking.py
```