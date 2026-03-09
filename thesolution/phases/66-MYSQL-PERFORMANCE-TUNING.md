# Phase 66: MySQL Performance Tuning (Percona Best Practices)

**Status**: IN PROGRESS (configs updated, restart needed for static settings)
**Priority**: Medium
**Depends on**: Phase 65/65B (bulk loader improvements)

## Problem

MySQL is running with mostly default settings. With 17M+ rows in `usaspending_award` (growing to 50-100M+), default configs leave significant performance on the table. Percona's research shows specific settings that can dramatically improve bulk load and query performance.

## Current vs Recommended Settings

### Buffer Pool

| Setting | Current | Recommended | Why |
|---------|---------|-------------|-----|
| `innodb_buffer_pool_size` | 4G | 50-60% of RAM (shared machine) | Keeps PK + hot indexes in memory. Already improved from 128MB default. |
| `innodb_buffer_pool_instances` | 8 (default) | 8 | Default is fine. 1-4 causes stalls per Percona benchmarks. |

### Redo Log

| Setting | Current | Recommended | Why |
|---------|---------|-------------|-----|
| `innodb_redo_log_capacity` | 100MB (default) | 2-4G | **Big win.** Default is far too small for bulk loads. When redo fills up, InnoDB does synchronous flushing at the worst time. Replaces deprecated `innodb_log_file_size`. Dynamic — no restart needed. |

### I/O Configuration

| Setting | Current | Recommended | Why |
|---------|---------|-------------|-----|
| `innodb_io_capacity` | 200 (default, HDD) | 2,000 (SATA SSD) or 10,000 (NVMe) | Tells InnoDB how fast your storage is. Default assumes spinning disk. |
| `innodb_io_capacity_max` | 2× io_capacity | 4,000 (SATA SSD) or 20,000 (NVMe) | Upper bound for background I/O bursts. Don't set excessively high — kills SSD lifespan. |
| `innodb_read_io_threads` | 4 (default) | 8 | More impactful on Windows (no libaio). |
| `innodb_write_io_threads` | 4 (default) | 8 | Same — Windows benefits more from higher values. |

### Change Buffer & Doublewrite

| Setting | Current | Recommended | Why |
|---------|---------|-------------|-----|
| `innodb_change_buffering` | all (default) | none | **SSD optimization.** Change buffer adds overhead for random writes that SSDs handle natively. Percona 8.4 defaults to `none`. |
| `innodb_doublewrite` | ON (default) | ON (keep) | Disabling yields ~50% write improvement BUT risks permanent data corruption on crash. Not worth the risk. |

### Adaptive Hash Index

| Setting | Current | Recommended | Why |
|---------|---------|-------------|-----|
| `innodb_adaptive_hash_index` | ON (default) | OFF | Percona 8.4 changed default to OFF. Becomes a contention source under concurrency and adds overhead during bulk inserts. |

### Sort & Index Creation

| Setting | Current | Recommended | Why |
|---------|---------|-------------|-----|
| `innodb_sort_buffer_size` | 1MB (default) | 4-8MB | Speeds up index rebuilds (CREATE INDEX). Relevant for `--fast` mode index recreation. Max 64MB. |
| `sort_buffer_size` | 256KB (default) | 256KB (keep) | Percona found performance **drops 50%** above 256KB. Leave at default. |
| `join_buffer_size` | 256KB (default) | 256KB (keep) | Fix slow joins with indexes, not buffer increases. |
| `read_buffer_size` | 128KB (default) | 128KB (keep) | Performance drops 50% at 2MB per Percona. Leave at default. |

### Temp Tables

| Setting | Current | Recommended | Why |
|---------|---------|-------------|-----|
| `tmp_table_size` | 16MB (default) | 64MB | Both must match. Larger allows more complex queries in-memory. |
| `max_heap_table_size` | 16MB (default) | 64MB | MySQL uses the lower of the two. |

### Connections & Cache

| Setting | Current | Recommended | Why |
|---------|---------|-------------|-----|
| `table_open_cache` | 4000 (default) | 4000 (keep) | Default is fine for our table count. |
| `thread_cache_size` | auto (default) | auto (keep) | Auto-sized since MySQL 5.6.8. Fine for our connection count. |
| `max_connections` | 151 (default) | 50-100 | We don't need 151. Lower reduces memory reservation. |

### Binary Logging & Durability (already done)

| Setting | Current | Recommended | Status |
|---------|---------|-------------|--------|
| `skip-log-bin` | SET | SET | Done in Phase 65B. No replication needed. |
| `innodb_undo_log_truncate` | ON | ON | Done in Phase 65B. |
| `innodb_max_undo_log_size` | 1G | 1G | Done in Phase 65B. |

## Implementation Plan

### Task 1: Update my.ini with Percona-recommended settings

- [x] Determine storage type — assumed NVMe (modern Win11 dev machine, io_capacity=10000). Comment in config notes SATA SSD alternative values.
- [x] Determine total system RAM — 4G buffer pool already correct for 16GB RAM machine (per reference sizing table).
- [x] Update `D:\mysql\my.ini` with all recommended settings (2026-03-08)
- [x] Update `thesolution/reference/mysql-my.ini` reference config with same settings + detailed comments (2026-03-08)
- [ ] Restart MySQL to apply static settings (`innodb_buffer_pool_instances=8`, `innodb_read/write_io_threads=8`)

### Task 2: Apply dynamic settings (no restart needed)

After restart (or immediately if MySQL is running), run these to apply dynamic settings without waiting for restart:

```sql
SET GLOBAL innodb_redo_log_capacity = 2147483648;
SET GLOBAL innodb_io_capacity = 10000;
SET GLOBAL innodb_io_capacity_max = 20000;
SET GLOBAL innodb_change_buffering = 'none';
SET GLOBAL innodb_adaptive_hash_index = OFF;
SET GLOBAL innodb_sort_buffer_size = 4194304;
SET GLOBAL tmp_table_size = 67108864;
SET GLOBAL max_heap_table_size = 67108864;
SET GLOBAL max_connections = 100;
```

Verify:
```sql
SHOW VARIABLES WHERE Variable_name IN (
  'innodb_redo_log_capacity', 'innodb_io_capacity', 'innodb_io_capacity_max',
  'innodb_change_buffering', 'innodb_adaptive_hash_index', 'innodb_sort_buffer_size',
  'tmp_table_size', 'max_heap_table_size', 'max_connections',
  'innodb_buffer_pool_instances', 'innodb_read_io_threads', 'innodb_write_io_threads'
);
```

- [ ] Apply dynamic settings via MySQL CLI
- [ ] Verify all settings match expected values

### Task 3: Validate performance improvement

- [ ] Run a bulk load (FY2025 or re-load a prior FY) and compare batch times
- [ ] Check `SHOW ENGINE INNODB STATUS` for checkpoint lag, redo log usage
- [ ] Monitor `Innodb_buffer_pool_reads` (should be near zero = all in memory)
- [ ] Check `Opened_tables` to verify table_open_cache is sufficient

### Task 4: Document final configuration

- [x] Update reference my.ini as the "production-ready" config template (2026-03-08)
- [ ] Record before/after batch times in this doc
- [ ] Note any settings that needed adjustment for this specific workload

## Proposed my.ini (complete)

```ini
[mysqld]
# === Buffer Pool ===
innodb_buffer_pool_size = 4G          # Adjust: 50-60% of RAM on shared machine
innodb_buffer_pool_instances = 8      # Default, good for 4G+

# === Redo Log ===
innodb_redo_log_capacity = 2G         # Default 100MB is way too small for bulk loads

# === I/O (adjust for your storage type) ===
# SATA SSD values shown. NVMe: use 10000/20000
innodb_io_capacity = 2000
innodb_io_capacity_max = 4000
innodb_read_io_threads = 8
innodb_write_io_threads = 8

# === InnoDB Optimizations ===
innodb_change_buffering = none         # SSD: change buffer adds unnecessary overhead
innodb_adaptive_hash_index = OFF       # Percona 8.4 default. Reduces contention.
innodb_sort_buffer_size = 4M           # Faster index rebuilds (CREATE INDEX)

# === Temp Tables ===
tmp_table_size = 64M
max_heap_table_size = 64M

# === Connections ===
max_connections = 100

# === Logging ===
skip-log-bin                           # No replication — eliminates binlog I/O
innodb_undo_log_truncate = ON
innodb_max_undo_log_size = 1G

# === File Access ===
secure-file-priv = ""                  # Allow LOAD DATA INFILE from any path
```

## Percona Toolkit (optional)

Consider installing Percona Toolkit for ongoing tuning:
- `pt-variable-advisor`: Scans SHOW VARIABLES and reports bad/suboptimal settings
- `pt-mysql-summary`: Comprehensive server health report
- `pt-config-diff`: Compare configs between servers
- Install: https://www.percona.com/software/database-tools/percona-toolkit

## Notes

- All `innodb_io_capacity` values assume SSD storage. If on spinning disk, use 200/400.
- `innodb_redo_log_capacity` replaced `innodb_log_file_size` + `innodb_log_files_in_group` in MySQL 8.0.30+. It's dynamic — can be changed without restart.
- Do NOT increase `sort_buffer_size` or `read_buffer_size` beyond defaults — Percona benchmarks show 50% performance drops at larger values.
- `innodb_doublewrite` should stay ON despite the write performance cost. Disabling risks permanent data corruption on crash.
- Percona's `innodb_dedicated_server=ON` auto-sizes buffer pool + redo log but assumes MySQL is the only app. Don't use on a dev machine.

## Sources

- Percona: InnoDB Performance Optimization Basics
- Percona: 10 MySQL Performance Tuning Settings After Installation
- Percona: How to Calculate a Good MySQL Redo Log Size
- Percona: innodb_buffer_pool_size — Is 80% of RAM the Right Amount?
- Percona: Give Love to Your SSDs — Reduce innodb_io_capacity_max
- Percona: Percona Server 8.4 Defaults and Tuning Guidance
- Percona: How to Load Large Files Safely into InnoDB with LOAD DATA INFILE
