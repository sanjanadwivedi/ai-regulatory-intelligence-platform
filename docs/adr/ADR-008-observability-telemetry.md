# ADR-008: Telemetry, Correlation Tracing, and Prometheus Observability

## Status
Accepted

## Context
Production enterprise deployments require real-time visibility into request latency, database query times, AI token consumption, and system errors.

## Decision
We implement:
1. **Prometheus Metrics Exporter** (`/metrics`) tracking HTTP request rates, error counts, and AI orchestrator pipeline calls.
2. **Correlation ID Tracking (`trace_id`)**: Injected into request headers (`X-Trace-ID`) and passed through to structured JSON logs.
3. **Container Health Probes** (`/health`) checking database and cache connectivity.

## Consequences
- **Positive**: Seamless integration with Datadog, Grafana, and Prometheus monitoring stacks.
- **Positive**: Rapid incident diagnosis using end-to-end trace IDs.
