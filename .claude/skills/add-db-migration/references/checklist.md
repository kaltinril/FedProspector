# Database Migration -- Checklist

## Before Creating Migration
- [ ] Identify target table and DDL file number (10-90)
- [ ] Check schema ownership (Python DDL vs EF Core)
- [ ] Determine next migration number (read migrations/ directory)
- [ ] Plan for FK dependencies (may need drop/re-add)

## Migration File
- [ ] Header comment with number, date, purpose
- [ ] Correct MySQL syntax (InnoDB, utf8mb4)
- [ ] Index naming follows convention (idx_, uk_, fk_)
- [ ] Use IF NOT EXISTS / IF EXISTS for idempotency
- [ ] AFTER clause for column positioning (optional but recommended)

## Base DDL Update
- [ ] Update corresponding `db/schema/tables/{nn}_*.sql` file
- [ ] Column definition matches migration exactly
- [ ] Index definition matches migration exactly

## Apply & Verify
- [ ] Apply: `mysql -u fed_app -p fed_contracts < db/schema/migrations/{file}.sql`
- [ ] Verify: `python main.py health check-schema --table {table} --verbose`
- [ ] No drift reported by schema checker

## If EF Core Table
- [ ] Also update C# entity model
- [ ] Also create EF Core migration (if applicable)
- [ ] Build C# solution to verify model compiles
