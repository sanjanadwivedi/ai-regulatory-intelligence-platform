# Production Deployment Guide

## Prerequisites
- Node.js 18+ (Frontend)
- Python 3.11+ (Backend)
- PostgreSQL 14+ (Production Database)
- Reverse Proxy (Nginx/Traefik) configured with SSL/TLS (HTTPS is strictly required).

## Mandatory Environment Variables
The following environment variables MUST be provided to the backend in production:
- `ENVIRONMENT`: Must be set to `production`.
- `SECRET_KEY`: A highly secure random 64+ character string. Defaults are explicitly blocked in production.
- `DATABASE_URL`: Connection string to the PostgreSQL database (e.g. `postgresql+asyncpg://user:pass@host:5432/db`).
- `FRONTEND_URL`: The exact origin of the frontend (e.g., `https://compliance.example.com`). Wildcards (`*`) are rejected.

## Database Setup & Migrations
1. Create a PostgreSQL database and user.
2. Provide the `DATABASE_URL` to the backend.
3. Run the integrity script to verify the schema:
   ```bash
   python backend/scripts/migrate_production_db.py
   ```

## Backend Startup
Use Uvicorn or Gunicorn with Uvicorn workers:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## Frontend Deployment
1. Install dependencies: `npm install`
2. Build the production application:
   ```bash
   npm run build
   ```
3. Serve the static contents of the `dist/` directory via Nginx or a CDN. Ensure that the API base URL is correctly targeted via environment variables or relative proxying.

## Health and Readiness Checks
- **Liveness (is the container running?):** `GET /health`
- **Readiness (is the database reachable?):** `GET /health/ready`

Use these endpoints for Kubernetes probes or Docker health checks.

## Logging & Monitoring
Logs are output as structured JSON by default. Forward these logs using standard agents (e.g., Promtail, Fluent Bit) to your log aggregator (e.g., Loki, ELK).

## Backup & Rollback
Refer to `docs/operations/backup_and_restore.md` for daily backup configurations. Rollback procedures involve pointing the application back to the restored database dump and, if applicable, reverting the container image to the previous version.
