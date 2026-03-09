# Add Data Field -- Layer Checklist

## Pre-Flight
- [ ] Determine field type using type-mapping.md
- [ ] Identify which entity/table the field belongs to
- [ ] Determine if field is business-meaningful (needs hash tracking)
- [ ] Determine which layers need the field (all, or subset)

## Layer 1: Python ETL
- [ ] Add to `_{ENTITY}_HASH_FIELDS` in loader (if business-meaningful)
- [ ] Add mapping in `_normalize_{entity}()` with correct parser
- [ ] Add to `_upsert_{entity}()` cols list
- [ ] Verify field name matches DB column name (snake_case)

## Layer 2: MySQL Database
- [ ] Add column to DDL file (`db/schema/tables/{nn}_{entity}.sql`)
- [ ] Create migration file (`db/schema/migrations/{NNN}_{description}.sql`)
- [ ] Add index if field will be filtered/searched
- [ ] Apply migration: `mysql -u fed_app -p fed_contracts < migration.sql`
- [ ] Verify: `python main.py health check-schema --table {entity}`

## Layer 3: C# Entity Model
- [ ] Add property to `api/src/FedProspector.Core/Models/{Entity}.cs`
- [ ] Add `[Column(TypeName = "...")]` for decimal types
- [ ] Add `[MaxLength(n)]` for VARCHAR types
- [ ] Property should be nullable (`?`) unless NOT NULL in DDL

## Layer 4: C# DTOs
- [ ] Add property to Detail DTO
- [ ] Add property to Search DTO (if shown in search results)
- [ ] Add property to Summary DTO (if shown in lists)
- [ ] Property type must match Entity model

## Layer 5: C# Service
- [ ] Add field mapping in service Select/projection
- [ ] If enriched from reference table, add join + lookup
- [ ] Verify mapping in both GetDetailAsync() and SearchAsync() if applicable

## Layer 6: React TypeScript Types
- [ ] Add property to interface in `ui/src/types/api.ts`
- [ ] Use camelCase (auto-converted from C# PascalCase)
- [ ] Mark as optional with `?` and `| null`

## Layer 7: React UI Component
- [ ] Add to display (facts array, grid column, or form field)
- [ ] Use appropriate formatter (formatCurrency, formatDate, etc.)
- [ ] Null fallback: `?? '--'` or `?? 'Unknown'`

## Verification
- [ ] Python tests pass: `pytest tests/ -k "{entity}"`
- [ ] C# builds: `dotnet build api/FedProspector.slnx`
- [ ] C# tests pass: `dotnet test api/FedProspector.slnx`
- [ ] TypeScript compiles: `cd ui && npx tsc --noEmit`
- [ ] Schema check: `python main.py health check-schema --table {entity}`

## File Path Reference

| Layer | Path Pattern |
|-------|-------------|
| Python loader | `fed_prospector/etl/{entity}_loader.py` |
| DDL | `fed_prospector/db/schema/tables/{nn}_{entity}.sql` |
| Migration | `fed_prospector/db/schema/migrations/{NNN}_{desc}.sql` |
| C# Entity | `api/src/FedProspector.Core/Models/{Entity}.cs` |
| C# DTOs | `api/src/FedProspector.Core/DTOs/{Entity}/` |
| C# Service | `api/src/FedProspector.Infrastructure/Services/{Entity}Service.cs` |
| TypeScript types | `ui/src/types/api.ts` |
| React pages | `ui/src/pages/{entity}/` |
