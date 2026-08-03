# ADR-005: Multi-Agent AI Pipeline Orchestration

## Status
Accepted

## Context
Single-prompt monolithic LLM calls suffer from context rot, hallucinations, and low explainability when attempting to summarize, extract obligations, score risk, map policies, and generate tasks simultaneously.

## Decision
We implement a **Multi-Agent AI Pipeline**:
- `ExtractionAgent`: Parses raw text into structured Regulatory Knowledge Ontology (`Section` → `Obligation` → `Requirement` → `Penalty`).
- `ClassificationAgent`: Evaluates statutory scope and risk exposure.
- `ImpactAgent`: Maps requirements into the Enterprise Knowledge Graph Chain.
- `RecommendationAgent`: Formulates actionable compliance tasks.

## Consequences
- **Positive**: High explainability with zero-hallucination guardrails and step-by-step auditability.
- **Positive**: Modular prompt optimization per agent.
