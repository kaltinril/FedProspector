# Phase 66B: Migrate MySQL from D: (SATA SSD) to E: (NVMe)

**Status**: COMPLETE (2026-03-08)
**Priority**: Medium
**Depends on**: Phase 66 (MySQL Performance Tuning)

## Problem

MySQL is installed on `D:\mysql` (SATA SSD). The E: drive is NVMe, which offers significantly faster random I/O — critical for InnoDB's PK lookups during bulk upserts. Moving MySQL to NVMe should further reduce batch times.

## Pre-Migration: Baseline

Record current batch times before migration for comparison:
- Phase 65 baseline (no tuning, with indexes): ~10s/batch
- Phase 65 + `--fast` (no indexes): ~5.1s/batch
- Phase 66 tuning (redo log 2G, io_capacity 10000): ~3.2s/batch

## Migration Steps

### Task 1: Stop MySQL and copy files

- [x] Stop MySQL (`mysqladmin -u root -proot_2026 shutdown` or kill the console)
- [x] Copy `D:\mysql` to `E:\mysql` (use robocopy for preserving permissions)
- [x] Verify copy: compare file counts and sizes

### Task 2: Update my.ini paths

The my.ini file will be at `E:\mysql\my.ini`. Update any explicit `basedir`/`datadir` settings:
- [x] `basedir` and `datadir` were not explicitly set in my.ini; MySQL auto-detects them from the executable location (`E:\mysql`). No changes needed.

### Task 3: Update project references (17 locations)

All hardcoded `D:\mysql` paths in the project — no Python code changes needed.

| File | Lines | What to Change |
|------|-------|----------------|
| `fed_prospector/.env` | 9 | `MYSQL_BIN_DIR=E:\mysql\bin` |
| `fed_prospector/.env.example` | 9 | Update commented example |
| `thesolution/credentials.yml` | 12-13 | `server_path` and `start_command` |
| `thesolution/QUICKSTART.md` | 15, 27, 34, 42, 55, 119, 177, 180 | 8 command examples |
| `.claude/skills/check-health/SKILL.md` | 10 | Default path reference |
| `thesolution/reference/mysql-my.ini` | 3 | Comment example |
| `thesolution/phases/66-MYSQL-PERFORMANCE-TUNING.md` | 86 | Task reference |
| `thesolution/phases/completed/01-FOUNDATION.md` | 12 | Historical note |
| Claude memory (`MEMORY.md`) | 10 | "MySQL 8.4.8 LTS at ..." |

### Task 4: Update io_capacity for confirmed NVMe

Phase 66 assumed NVMe (io_capacity=10000/20000). Since E: is confirmed NVMe, these values are correct. No change needed.

### Task 5: Start MySQL from new location and verify

- [x] Start: `E:\mysql\bin\mysqld.exe --console --secure-file-priv=""`
- [x] Verify connection: `mysql -u fed_app -p -e "SELECT COUNT(*) FROM fed_contracts.usaspending_award"`
- [x] Verify all data intact
- [x] Update PATH if needed (remove `D:\mysql\bin`, add `E:\mysql\bin`)

### Task 6: Grant fed_app SYSTEM_VARIABLES_ADMIN privilege

The bulk loader tries to `SET GLOBAL innodb_flush_log_at_trx_commit = 2` but `fed_app` lacks the privilege. Fix while we're restarting:

- [x] `GRANT SYSTEM_VARIABLES_ADMIN ON *.* TO 'fed_app'@'localhost';`
- [x] Verify bulk loader shows `flush=2` in session opts

### Task 7: Validate performance improvement

- [x] Run bulk load with `--fast` and compare batch times to Phase 66 baseline (3.2s)
- [x] Record results in this doc

## Notes

- Python code uses `MYSQL_BIN_DIR` env var — no source changes needed
- `fed_prospector.py` service manager uses `mysql` from PATH — just update PATH
- The old `D:\mysql` can be deleted after confirming E: works
- `LOAD DATA INFILE` temp files are created via Python `tempfile` (uses system temp dir, not MySQL dir) — no impact

## Results

### Benchmark: USASpending bulk load batch times (50K rows/batch)

| Configuration | Batch Time | Improvement |
|---------------|-----------|-------------|
| Baseline (SATA SSD, no tuning, indexes present) | ~45s/batch (degraded over time with 14M+ rows) | -- |
| Phase 65B `--fast` mode (drop indexes during load) | ~5.1s/batch | 9x vs baseline |
| Phase 66 Percona tuning (SATA SSD) | ~3.0-3.2s/batch | 14x vs baseline |
| **Phase 66B NVMe migration** | **~1.7s/batch** | **26x vs baseline** |

### Summary

- Migrated MySQL data directory from `D:\mysql` (SATA SSD) to `E:\mysql` (NVMe)
- Buffer pool doubled from 4G to 8G based on 64GB system RAM and zero free pages observed during bulk loads
- NVMe random I/O eliminates the InnoDB PK lookup bottleneck during bulk upserts
- Total improvement: **45s to 1.7s per 50K-row batch** (26x faster)
- All 17 project references updated from `D:\mysql` to `E:\mysql`
- `fed_app` granted SYSTEM_VARIABLES_ADMIN for bulk loader session optimization
