# Production Environment Reference

This document outlines the strict environmental contract required to deploy the AI-Powered Regulatory Intelligence Platform to production.

## Application Configuration

| Variable | Description | Production Requirement |
|---|---|---|
| `ENVIRONMENT` | Specifies the application runtime environment. | Must be set to `production`. |
| `DEBUG` | Controls application debug logging and exception traces. | **Must be `False`**. Config is hard-coded to force `False` if `ENVIRONMENT="production"`. |
| `SECRET_KEY` | Cryptographic signing key for JWT and sessions. | **Must be randomly generated securely** (e.g. `openssl rand -hex 32`). Must NOT be default. Startup will fail if default. |

## Network & Routing

| Variable | Description | Production Requirement |
|---|---|---|
| `FRONTEND_URL` | The public base URL where the frontend is hosted. | Required for strict CORS policies. Wildcards (`*`) are prohibited in production. |

## Database Configuration

| Variable | Description | Production Requirement |
|---|---|---|
| `DATABASE_URL` | Full SQLAlchemy connection string. | Must point to PostgreSQL (e.g. `postgresql://user:pass@db:5432/dbname`). Do not log credentials. |
| `POSTGRES_DB` | Name of the PostgreSQL database. | E.g. `compliance_db` |
| `POSTGRES_USER` | PostgreSQL user account. | Use a dedicated, least-privilege user. |
| `POSTGRES_PASSWORD` | PostgreSQL user password. | Must be securely generated and injected via secrets manager or `.env`. Never commit this. |

## External Services & AI

| Variable | Description | Production Requirement |
|---|---|---|
| `GEMINI_API_KEY` | Primary API key for Gemini models. | Required for AI engine. Must be kept secret. |
| `SECONDARY_LLM_PROVIDER` | Fallback model provider. | Optional depending on SLA needs. |
| `SECONDARY_LLM_API_KEY` | API key for fallback provider. | Optional. |

## Security Hardening
- **Never commit `.env` to version control.**
- **Avoid wildcard CORS:** Ensure `FRONTEND_URL` strictly matches your reverse proxy domain.
- **Do not output credentials to logs:** `DATABASE_URL` is parsed by the application but is stripped from standard output logs.
