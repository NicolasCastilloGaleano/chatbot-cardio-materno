# adapter outbound: rag

Implementa los puertos `KnowledgeRetriever` y `Embedder` (ADR 0008):
- `hybrid_retriever.py`: coseno (numpy) + BM25 + RRF + umbral de `knowledge/evidence_policy.json`.
- `vector_index.py` / `kb_index_builder.py`: índice propio en `data/kb_index/` (no versionado).
- `ollama_embedder.py`: `/api/embed` con división de lotes ante timeouts.
- `knowledge_files.py`: lee `knowledge/kb/entries.jsonl` y la política.
