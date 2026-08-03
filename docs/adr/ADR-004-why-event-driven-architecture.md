# ADR-004: Event-Driven Decoupling Between Decision & Workflow Domains

## Status
Accepted

## Context
In monolithic feature designs, impact analysis directly invokes task creation logic. This violates DDD rules by allowing the Decision Domain to own Workflow logic.

## Decision
We enforce an **Event-Driven Architecture**:
1. `Compliance Decision Domain` performs multi-agent assessment and emits `ImpactAssessedEvent`.
2. `Compliance Workflow Domain` consumes `ImpactAssessedEvent` and independently evaluates task generation rules.

## Consequences
- **Positive**: Complete domain decoupling; decision logic remains pure without workflow side-effects.
- **Positive**: Enables adding new event consumers (e.g. SIEM alerts, Slack push notifications) without modifying decision code.
