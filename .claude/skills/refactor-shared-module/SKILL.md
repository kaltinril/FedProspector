---
name: refactor-shared-module
description: "Safely refactor FedProspect's critical shared modules (connection.py, settings.py, staging_mixin.py, change_detector.py, load_manager.py, etl_utils.py, base_client.py) with blast-radius awareness. Use this skill whenever modifying, refactoring, or changing any of these 7 shared modules, or when the user mentions refactoring connection, settings, staging, change detection, load manager, ETL utils, or the base API client."
argument-hint: "<module-name> [description of change]"
disable-model-invocation: true
---

# Refactor Shared Module

Safely refactor one of the 7 critical shared modules that have wide blast radius across the codebase. A single mistake can silently break 9-35 downstream files.

## Arguments

Parse `$ARGUMENTS`:

| Argument | Example | Purpose |
|----------|---------|---------|
| module-name | `staging_mixin` | Which shared module to refactor |
| description | `add retry logic` | What change is being made |

Valid modules: `connection`, `settings`, `staging_mixin`, `change_detector`, `load_manager`, `etl_utils`, `base_client`

## Workflow

### Step 1: Read impact map
Read `references/dependency-map.md` to understand which files import this module and how many consumers will be affected.

### Step 2: Read critical patterns
Read `references/critical-patterns.md` for invariants that MUST be preserved in this module. Violating these causes silent bugs.

### Step 3: Scan all consumers
Before making any change, grep for all imports of this module to build the complete impact list:
```bash
cd fed_prospector && grep -r "from {module_path} import" --include="*.py" -l
```

### Step 4: Assess the change
For each downstream consumer, determine if the change:
- **Breaks API**: Method signature change, removed method, renamed constant -> must update all consumers
- **Extends API**: New method/parameter with defaults -> safe, no consumer updates needed
- **Internal only**: Implementation change, same interface -> safe if critical patterns preserved

### Step 5: Make the change
Apply the refactoring to the shared module. Preserve all critical patterns listed in `references/critical-patterns.md`.

### Step 6: Update consumers (if breaking)
If the change breaks the API, update ALL downstream consumers. Do not leave any file unmodified.

### Step 7: Verify
Run tests for all affected consumers:
```bash
cd fed_prospector && python -m pytest tests/ -v --tb=short
```

For base_client changes, also verify all API clients:
```bash
python -c "from api_clients.sam_opportunity_client import SAMOpportunityClient; print('OK')"
python -c "from api_clients.usaspending_client import USASpendingClient; print('OK')"
```

## Blast Radius Summary

| Module | Consumers | Risk Level |
|--------|-----------|-----------|
| `db/connection.py` | 35 files | CRITICAL |
| `config/settings.py` | 21 files | CRITICAL |
| `etl/load_manager.py` | 20 files | HIGH |
| `api_clients/base_client.py` | 13 files | HIGH |
| `etl/change_detector.py` | 9 files | HIGH |
| `etl/etl_utils.py` | 9 files | MEDIUM |
| `etl/staging_mixin.py` | 8 files | HIGH |

## Quick Reference
See `references/dependency-map.md` for exact file lists and `references/critical-patterns.md` for invariants.
