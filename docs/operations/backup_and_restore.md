# Backup & Recovery Procedures

## Recovery Point Objective (RPO) & Recovery Time Objective (RTO)
- **RPO**: Recommended 24 hours (daily backups), or 1 hour for high-criticality environments using Write-Ahead Log (WAL) archiving in PostgreSQL.
- **RTO**: Less than 4 hours from disaster declaration to full service restoration.

## SQLite Backup Strategy (Small Deployments)
SQLite data is stored in a single file (`compliance_platform.db` by default).

### Backup
Do not simply copy the file while the application is running, as it might be corrupted due to partial writes. Use the sqlite3 CLI:
```bash
sqlite3 compliance_platform.db ".backup 'compliance_platform_backup.db'"
```

### Restore
Stop the backend application, then overwrite the original database file:
```bash
cp compliance_platform_backup.db compliance_platform.db
```
Restart the application.

## PostgreSQL Backup Strategy (Production Deployments)

### Backup using `pg_dump`
Schedule a daily `cron` job to dump the database:
```bash
pg_dump -U compliance_user -F c -b -v -f /backups/compliance_db_$(date +%Y%m%d).backup compliance_db
```

### Restore using `pg_restore`
In the event of a catastrophic failure:
1. Stop the backend application to prevent connections.
2. Drop the existing corrupted database and recreate it.
3. Run `pg_restore`:
```bash
pg_restore -U compliance_user -d compliance_db -1 /backups/compliance_db_20260824.backup
```

## Backup Retention & Encryption
- Keep daily backups for 30 days.
- Encrypt backups at rest using tools like `gpg` or cloud-provider encryption mechanisms (e.g., AWS KMS) before moving them to off-site storage.

## Testing Restore Procedures
Quarterly disaster recovery testing is mandatory. Spin up an isolated staging environment and perform a complete restore to ensure data integrity.
