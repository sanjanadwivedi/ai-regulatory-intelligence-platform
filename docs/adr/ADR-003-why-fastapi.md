# ADR-003: Selection of FastAPI as Core Web Framework

## Status
Accepted

## Context
The platform backend requires high throughput, async IO support for external regulator feed crawling and AI inference calls, automatic OpenAPI documentation, and strict runtime data validation.

## Decision
We select **Python FastAPI** with Pydantic v2 data models and Async/Sync SQLAlchemy ORM.

## Consequences
- **Positive**: Native async execution, high concurrency, and automatic Swagger OpenAPI documentation.
- **Positive**: Seamless integration with Python AI/NLP libraries (LangChain, PyTorch, Transformers).
- **Negative**: Requires explicit Pydantic data contract management across domain boundaries.
