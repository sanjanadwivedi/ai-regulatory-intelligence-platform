# ADR-001: Adoption of Domain-Driven Design (DDD)

## Status
Accepted

## Context
Enterprise regulatory change management involves complex business capabilities across multiple regulatory authorities (RBI, SEC, EBA), internal compliance policies, risk registers, and operational approval workflows. A generic feature-driven monolith creates tightly coupled logic where regulatory ingestion, AI analysis, policy mapping, and task management bleed into one another.

## Decision
We adopt **Domain-Driven Design (DDD)** as the primary architectural pattern. The system is partitioned into 8 explicit Bounded Contexts:
1. `Regulatory Intelligence Domain`
2. `Regulatory Knowledge Domain`
3. `Organization Context Domain`
4. `Compliance Decision Domain`
5. `Compliance Workflow Domain`
6. `Identity & Security Domain`
7. `Notification Domain`
8. `Reporting & Audit Domain`

## Consequences
- **Positive**: Strict isolation of business capabilities, preventing feature clutter and technical leakage.
- **Positive**: Direct alignment between domain code models and Compliance Officer mental models.
- **Negative**: Requires formal event-driven decoupling and explicit Anti-Corruption Layers (ACL).
