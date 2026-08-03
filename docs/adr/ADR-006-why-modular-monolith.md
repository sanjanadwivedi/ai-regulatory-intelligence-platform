# ADR-006: Modular Monolith Strategy for System Delivery

## Status
Accepted

## Context
Deploying full microservices infrastructure (Kubernetes, distributed tracing, network mesh) early in platform development introduces premature operational overhead, latency, and debugging friction.

## Decision
We implement a **Modular Monolith**:
- Single deployable artifact containing strictly partitioned Bounded Context packages (`shared_kernel`, `acl`, `domains`).
- In-memory event bus and database boundary separation.

## Consequences
- **Positive**: Simple local execution (`python app/main.py`), zero network hop overhead, rapid iteration.
- **Positive**: Clear migration path to distributed microservices if scaling requirements demand independent service deployments.
