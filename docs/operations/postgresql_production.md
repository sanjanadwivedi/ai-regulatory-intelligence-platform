# PostgreSQL Production Guidelines

This document outlines the requirements and recommended configurations for running PostgreSQL in production for the AI-Powered Regulatory Intelligence Platform.

## PostgreSQL Configuration
- **Version**: PostgreSQL 16+ is highly recommended (compatible with `pgvector` for AI similarity features if needed).
- **Database Engine**: SQLAlchemy is used for ORM. The production driver must be `psycopg2` or `asyncpg` (use `postgresql+psycopg2://` or `postgresql+asyncpg://` in `DATABASE_URL`).
- **Connection Pooling**: SQLAlchemy maintains a connection pool. 
  - `pool_pre_ping=True` MUST be set in production to prevent stale connections in long-running containerized environments.
  - `pool_recycle` should be set (e.g., 3600 seconds) to proactively close old connections.
- **Extensions**: If similarity search/AI embeddings are used locally rather than through LLM APIs, ensure the `pgvector` extension is enabled in the database (`CREATE EXTENSION vector;`).

## Security & Permissions
- **Dedicated Application User**: Never run the application using the `postgres` superuser role.
- **Least Privilege**:
  ```sql
  CREATE USER compliance_app WITH PASSWORD 'SECURE_PASSWORD_HERE';
  CREATE DATABASE compliance_db OWNER compliance_app;
  GRANT ALL PRIVILEGES ON DATABASE compliance_db TO compliance_app;
  ```
- **Network Isolation**: PostgreSQL should run on an internal Docker bridge network or private VPC subnet. Do not expose port `5432` to the public internet.

## Database URL Format
The production `DATABASE_URL` environment variable must follow this structure:
`postgresql://compliance_app:SECURE_PASSWORD_HERE@db:5432/compliance_db`

## Migrations Workflow
Since the repository relies on SQLAlchemy metadata creation rather than Alembic versioned migrations:
- Run `python backend/scripts/migrate_production_db.py` to initialize the database schema.
- **Never drop tables** manually in production. `Base.metadata.create_all()` is safe as it will not overwrite existing tables.
- For future schema changes, write explicit `ALTER TABLE` scripts or implement Alembic if required.

## Backups & Restores
- **Backup Procedure**: Use `pg_dump` via a scheduled cron job or container.
  ```bash
  docker exec -t compliance-db pg_dump -U compliance_app compliance_db > /backups/db_backup_$(date +%Y%m%d).sql
  ```
- **Restore Procedure**: Use `psql` to import data to a fresh database.
  ```bash
  cat /backups/db_backup_xxxx.sql | docker exec -i compliance-db psql -U compliance_app -d compliance_db
  ```
- **Integrity**: Validate backups routinely by restoring them into a staging environment and running the production integrity script (`python backend/scripts/check_production_integrity.py`).
