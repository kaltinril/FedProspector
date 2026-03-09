---
name: add-db-migration
description: "Create a MySQL database migration for FedProspect: generates numbered migration SQL file, applies to live database, and verifies with schema checker. Use this skill whenever the user wants to alter a table, add a column, create an index, add a foreign key, fix schema drift, or make any database schema change."
argument-hint: "<description> [--table=TableName] [--type=add-column|add-index|add-table|alter-column|drop-column]"
disable-model-invocation: true
---

# Add Database Migration

## Arguments

Parse `$ARGUMENTS`:

| Argument | Example | Purpose |
|----------|---------|---------|
| description | `add_estimated_value_to_opportunity` | Migration description (used in filename) |
| --table | `opportunity` | Target table name |
| --type | `add-column` | Migration type hint |

Derive:
- Next migration number: Read `fed_prospector/db/schema/migrations/`, find highest NNN prefix, increment
- Filename: `{NNN}_{description}.sql`

## Workflow

### Step 1: Read conventions
Read `references/conventions.md` for MySQL syntax, naming, and DDL organization.

### Step 2: Determine migration number
List files in `fed_prospector/db/schema/migrations/` to find the next available number. Use zero-padded 3-digit format (e.g., `016`, `017`).

### Step 3: Generate migration SQL
Create `fed_prospector/db/schema/migrations/{NNN}_{description}.sql` with:
- Header comment (migration number, description, date)
- SQL statements following project conventions (InnoDB, utf8mb4)
- Use IF NOT EXISTS / IF EXISTS for idempotency where possible

### Step 4: Update base DDL
Also update the corresponding table DDL file in `fed_prospector/db/schema/tables/` so the base schema stays in sync with the migration.

### Step 5: Apply migration
```bash
cd fed_prospector && mysql -u fed_app -p fed_contracts < db/schema/migrations/{NNN}_{description}.sql
```

### Step 6: Verify with schema checker
```bash
cd fed_prospector && python main.py health check-schema --table {table_name} --verbose
```

## DDL File Organization

| Prefix | Domain | Tables |
|--------|--------|--------|
| 10_ | Reference/Lookup | NAICS, PSC, country, state, FIPS, SBA |
| 20_ | Entity | SAM.gov contractor master data |
| 30_ | Opportunities | Contract opportunities |
| 40_ | Federal Contracts | FPDS contracts, federal orgs |
| 50_ | ETL Operations | Load logs, errors, quality rules, rate limits |
| 55_ | Data Load Requests | Load request tracking |
| 60_ | Prospecting/CRM | Organization, users, prospects, saved searches |
| 70_ | USASpending | Awards, transactions |
| 80_ | Raw Staging | stg_*_raw tables |
| 90_ | Web API | Sessions, proposals, notifications |

## Conventions

| Rule | Detail |
|------|--------|
| Engine | `ENGINE=InnoDB` |
| Charset | `DEFAULT CHARSET=utf8mb4` |
| Index naming | `idx_{table}_{column}` |
| Unique key naming | `uk_{table}_{column}` |
| Foreign key naming | `fk_{table}_{column}` |
| Idempotency | Use `IF NOT EXISTS` / `IF EXISTS` where possible |
| FK changes | Drop FK first, modify column, re-add FK |
| Schema checker | Always run after applying: `python main.py health check-schema` |

## Quick Reference
See `references/checklist.md` for common migration patterns.
