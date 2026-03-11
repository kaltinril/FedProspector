# Backup and Recovery

## Quick Reference

| Item | Value |
|------|-------|
| Database | `fed_contracts` on MySQL 8.4 |
| Backup tool | `mysqldump` via `fed_prospector/scripts/backup_db.py` |
| Restore tool | `fed_prospector/scripts/restore_db.py` |
| Default location | `backups/` (project root, git-ignored) |
| File format | `fed_contracts_YYYYMMDD_HHMMSS.sql.gz` |
| Retention | 30 days (configurable) |

## Running Backups

### Manual

```bash
cd c:\git\fedProspect\fed_prospector
python scripts/backup_db.py                     # default settings
python scripts/backup_db.py --retain-days 14    # keep only 14 days
python scripts/backup_db.py --backup-dir E:\backups  # custom location
```

Override backup directory via `BACKUP_DIR` environment variable or `--backup-dir` flag.

### Scheduled (Windows Task Scheduler)

1. Open Task Scheduler, create a new task named `FedProspect DB Backup`
2. Trigger: Daily at 02:00
3. Action: Start a program
   - Program: `python`
   - Arguments: `scripts/backup_db.py`
   - Start in: `c:\git\fedProspect\fed_prospector`
4. Run whether user is logged on or not

### Recommended Schedule

Daily backups are sufficient for this workload. The database is populated from government APIs that can be re-loaded if needed, so RPO (recovery point objective) is relaxed.

## Restoring

```bash
cd c:\git\fedProspect\fed_prospector

# Interactive (asks for confirmation)
python scripts/restore_db.py ../backups/fed_contracts_20260310_020000.sql.gz

# Non-interactive
python scripts/restore_db.py ../backups/fed_contracts_20260310_020000.sql.gz --yes
```

Both `.sql.gz` and plain `.sql` files are supported.

## Storage

Backups are stored in `backups/` at the project root (git-ignored). For off-site protection, copy backups to a second drive or cloud storage periodically. A typical compressed backup is well under 1 GB for this dataset.
