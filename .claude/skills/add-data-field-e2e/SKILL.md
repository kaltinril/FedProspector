---
name: add-data-field-e2e
description: "Add a new data field across the full FedProspect stack: Python ETL loader, MySQL DDL, C# entity/DTO/service, React TypeScript type, and UI component. Use this skill whenever the user wants to add a new column, property, or field that flows from ETL data through to the UI, or needs to add a field at any layer and wants to ensure all layers stay in sync."
argument-hint: "<FieldName> <EntityName> [--type=string|decimal|date|datetime|int|bool|json] [--layers=all|python|db|csharp|react]"
disable-model-invocation: true
---

# Add Data Field End-to-End

Guides adding a new data field across all layers of the FedProspect stack, ensuring type consistency and no layer is missed.

## Arguments

Parse `$ARGUMENTS`:

| Argument | Example | Purpose |
|----------|---------|---------|
| FieldName | `estimated_value` | snake_case field name (DB column name) |
| EntityName | `opportunity` | snake_case entity/table name |
| --type | `decimal` | Data type (default: string). Options: string, decimal, date, datetime, int, bool, json |
| --layers | `all` | Which layers to modify (default: all) |

Derive names:
- Python: `estimated_value` (snake_case)
- MySQL column: `estimated_value` (snake_case)
- C# property: `EstimatedValue` (PascalCase)
- TypeScript: `estimatedValue` (camelCase)
- Display label: `Estimated Value` (Title Case)

## Workflow

### Step 1: Read reference files
Read `references/type-mapping.md` for cross-layer type equivalences. Read `references/layer-checklist.md` for the step-by-step process.

### Step 2: Python ETL layer
In `fed_prospector/etl/{entity}_loader.py`:
1. Add field to `_{ENTITY}_HASH_FIELDS` list (if business-meaningful)
2. Add field mapping in `_normalize_{entity}()` with appropriate parser (parse_date, parse_decimal, etc.)
3. Add column name to `_upsert_{entity}()` cols list

### Step 3: MySQL DDL
1. Add column definition to `fed_prospector/db/schema/tables/{nn}_{entity}.sql`
2. Create migration in `fed_prospector/db/schema/migrations/` with ALTER TABLE
3. Add index if the field will be filtered/searched
4. Apply migration to live database

### Step 4: C# Entity model
In `api/src/FedProspector.Core/Models/{Entity}.cs`:
- Add property with correct type and attributes (e.g., `[Column(TypeName = "decimal(15,2)")]`)

### Step 5: C# DTO
In `api/src/FedProspector.Core/DTOs/{Entity}/`:
- Add property to relevant DTOs (Detail, Search, Summary as appropriate)

### Step 6: C# Service mapping
In `api/src/FedProspector.Infrastructure/Services/{Entity}Service.cs`:
- Add field mapping in LINQ Select projections (e.g., `EstimatedValue = opp.EstimatedValue`)

### Step 7: React TypeScript type
In `ui/src/types/api.ts`:
- Add property to relevant interface (e.g., `estimatedValue?: number | null;`)

### Step 8: React component display
In the relevant page/component:
- Add field to display (facts array, grid column, form field)
- Use appropriate formatter (formatCurrency, formatDate, etc.)

### Step 9: Verify
```bash
cd fed_prospector && python -m pytest tests/ -k "{entity}" -v
cd api && dotnet build && dotnet test
cd ui && npx tsc --noEmit
```

## Conventions

| Rule | Detail |
|------|--------|
| Nullable by default | All new fields nullable unless explicitly required |
| Hash fields | Add to hash list ONLY if the field represents a business-meaningful change |
| Type consistency | Use the type-mapping reference — mismatches cause silent bugs |
| Naming | Python/MySQL: snake_case, C#: PascalCase, TypeScript: camelCase |
| Display fallback | Always use `?? '--'` or `?? 'Unknown'` for null display |

## Quick Reference
See `references/layer-checklist.md` for a condensed per-layer checklist.
