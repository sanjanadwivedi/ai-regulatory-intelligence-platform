# ADR-009: RAG AI Evaluation Harness & Benchmark Suite

## Status
Accepted

## Context
Deploying LLM RAG pipelines in high-stakes regulatory compliance requires empirical validation of accuracy, citation grounding, and hallucination rates before pushing prompt updates to production.

## Decision
We build an automated **RAG AI Evaluation Harness** (`backend/tests/test_ai_eval.py`) that evaluates LLM responses against benchmark statutory Q&A pairs measuring 3 metrics:
1. **Faithfulness Score**: Verifies every assertion is directly backed by source section text.
2. **Answer Relevance**: Measures semantic alignment with compliance query intent.
3. **Hallucination Detection Rate**: Enforces < 0.01% hallucination rate threshold.

## Consequences
- **Positive**: Prevents regression in AI extraction accuracy during prompt tuning or model upgrades.
- **Positive**: Provides mathematical confidence metrics for Compliance Officers and Auditors.
