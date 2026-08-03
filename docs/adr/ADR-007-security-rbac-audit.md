# ADR-007: Role-Based Access Control (RBAC) and Immutable Audit Ledger

## Status
Accepted

## Context
Enterprise compliance operations require strict segregation of duties (4-Eyes principle) and immutable audit trails for SOC2 Type II, GDPR, and statutory regulator examinations.

## Decision
We enforce:
1. **Strict Role-Based Access Control (RBAC)** across 5 enterprise personas (`Compliance Officer`, `Chief Compliance Officer`, `General Counsel`, `Internal Auditor`, `System Administrator`).
2. **Cryptographic Append-Only Audit Ledger** recording every user action, workflow state transition, and AI decision with user attribution and UTC timestamps.

## Consequences
- **Positive**: Complete auditability for external regulatory examiners and zero unauthorized state transitions.
- **Negative**: Adds database write overhead for every state mutation.
