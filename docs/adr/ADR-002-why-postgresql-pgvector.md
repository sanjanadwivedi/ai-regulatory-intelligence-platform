# ADR-002: PostgreSQL + pgvector for Relational and Semantic Storage

## Status
Accepted

## Context
The platform requires both transactional relational integrity (regulations, tasks, user sign-offs, audit logs) and high-performance vector semantic search for Retrieval-Augmented Generation (RAG). Using a separate standalone vector database (e.g. Pinecone or Qdrant) alongside a relational database introduces data synchronization overhead, dual-write complexities, and extra infrastructure management.

## Decision
We select **PostgreSQL with the `pgvector` extension** (with SQLite + serialized vector fallback for zero-dependency local development).

## Consequences
- **Positive**: Single unified database engine handling relational joins, JSON metadata, and vector similarity queries.
- **Positive**: Transactional consistency across regulations, knowledge graph links, and vector embeddings.
- **Negative**: High-dimensional vector indexing (IVFFlat/HNSW) requires memory tuning in large-scale deployments.
