# Database Migration Conventions

## MySQL Standards
- Engine: InnoDB (transaction support, FK enforcement)
- Character set: utf8mb4 (full Unicode support)
- Collation: utf8mb4_0900_ai_ci (MySQL 8.0+ default) or utf8mb4_unicode_ci
- All timestamps: `DATETIME DEFAULT CURRENT_TIMESTAMP`

## Migration File Format

```sql
-- Migration {NNN}: {Brief title}
-- Applied: {YYYY-MM-DD}
-- Purpose: {What this migration does and why}

-- {SQL statements}
```

## Common Data Types

| Use Case | MySQL Type | Example |
|----------|-----------|---------|
| Short text | `VARCHAR(n)` | `VARCHAR(100)` for names, codes |
| Long text | `TEXT` or `LONGTEXT` | Descriptions, raw content |
| Currency | `DECIMAL(15,2)` | Award amounts, budgets |
| Integer | `INT` | Counts, quantities |
| Date only | `DATE` | Posted dates, deadlines |
| Date+time | `DATETIME` | Timestamps, audit trails |
| Boolean flag | `CHAR(1)` | 'Y'/'N' pattern |
| Hash | `CHAR(64)` | SHA-256 record hash |
| JSON data | `JSON` | Complex nested data |
| UUID/ID | `VARCHAR(100)` | External IDs (notice_id, UEI) |

## Index Naming Conventions
- Regular index: `idx_{table}_{column}` (e.g., `idx_opp_posted_date`)
- Unique index: `uk_{table}_{column}` (e.g., `uk_excl_key`)
- Foreign key: `fk_{table}_{column}` (e.g., `fk_opp_load_id`)
- Composite: `idx_{table}_{col1}_{col2}`

## Common Migration Patterns

### Add Column
```sql
ALTER TABLE {table_name}
    ADD COLUMN {column_name} {TYPE} AFTER {existing_column};
```

### Add Index
```sql
ALTER TABLE {table_name}
    ADD INDEX idx_{table}_{column} ({column_name});
```

### Add Unique Constraint
```sql
ALTER TABLE {table_name}
    ADD UNIQUE INDEX uk_{table}_{column} ({column_name});
```

### Modify Column Type
```sql
ALTER TABLE {table_name}
    MODIFY COLUMN {column_name} {NEW_TYPE};
```

### Add Foreign Key
```sql
ALTER TABLE {table_name}
    ADD CONSTRAINT fk_{table}_{column}
    FOREIGN KEY ({column_name}) REFERENCES {ref_table}({ref_column});
```

### Drop and Re-add FK (for column type changes)
```sql
ALTER TABLE {table_name} DROP FOREIGN KEY fk_{table}_{column};
ALTER TABLE {table_name} MODIFY COLUMN {column_name} {NEW_TYPE};
ALTER TABLE {table_name} ADD CONSTRAINT fk_{table}_{column}
    FOREIGN KEY ({column_name}) REFERENCES {ref_table}({ref_column});
```

### Create New Table
```sql
CREATE TABLE IF NOT EXISTS {table_name} (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    {columns...},
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

## Standard Metadata Columns
Tables that track ETL data should include:
```sql
record_hash      CHAR(64),
first_loaded_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
last_loaded_at   DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
last_load_id     INT,
```

## Schema Ownership Rules
- **Python DDL owns**: ETL tables (entity, opportunity, fpds_contract, usaspending_*, stg_*, etl_*, ref_*)
- **EF Core owns**: Application tables (app_user, prospect, prospect_note, saved_search, organization, etc.)
- **Both read**: Reference tables are populated by Python, read by C# API
- When adding columns to EF-owned tables, also create an EF Core migration

## Schema Checker Integration
After any migration, verify with:
```bash
python main.py health check-schema --table {table} --verbose
python main.py health check-schema  # full check
```

The checker compares DDL files against live DB and reports:
- Missing tables, columns, indexes, foreign keys, views
- Type mismatches between DDL and live schema
- Use `--fix` to generate remediation SQL
