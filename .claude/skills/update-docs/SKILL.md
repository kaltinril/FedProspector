---
name: update-docs
description: "Audit and update all project documentation after changes: CLAUDE.md, MASTER-PLAN.md, QUICKSTART.md, MEMORY.md, and skill files. Scans for stale counts and updates them. Use after completing any code changes that affect counts, file paths, or conventions. Usage: /update-docs [description of what changed]"
argument-hint: "[description of what changed]"
context: fork
agent: coder
---

# Update Documentation Skill

Audit and update all project documentation after code changes. This is the user's #1 instruction: "Always update ALL docs after completing work."

## Arguments

`$ARGUMENTS` = optional description of what changed (helps focus the audit). If empty, perform a full audit of all counts and values.

## Step 1: Get Current Counts

Run these commands to determine the actual current values. Run them in parallel where possible.

| Metric | How to Count |
|--------|-------------|
| Python tests | `python -m pytest c:/git/fedProspect/fed_prospector/tests/ --collect-only -q 2>/dev/null \| tail -1` |
| C# Core tests | `dotnet test c:/git/fedProspect/api/tests/FedProspector.Core.Tests/ --list-tests 2>/dev/null \| grep -c "^  "` |
| C# Api tests | `dotnet test c:/git/fedProspect/api/tests/FedProspector.Api.Tests/ --list-tests 2>/dev/null \| grep -c "^  "` |
| C# Infra tests | `dotnet test c:/git/fedProspect/api/tests/FedProspector.Infrastructure.Tests/ --list-tests 2>/dev/null \| grep -c "^  "` |
| Endpoints | Count `[Http` attributes: `grep -r "\[Http" c:/git/fedProspect/api/src/FedProspector.Api/Controllers/ \| grep -v "//"` |
| Controllers | Count controller files: `ls c:/git/fedProspect/api/src/FedProspector.Api/Controllers/*Controller.cs \| wc -l` (minus ApiControllerBase) |
| Tables + Views | MySQL: `SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='fed_contracts'` (or count DDL files) |
| CLI commands | `grep -r "@click.command\|@click.group" c:/git/fedProspect/fed_prospector/cli/ \| grep -c command` |

Compute the total test count as the sum of Python + C# Core + C# Api + C# Infra.

## Step 2: Audit Each Doc File

For each file, grep for the current count patterns and compare with the actual values from Step 1.

### `c:/git/fedProspect/CLAUDE.md`

Values to check (with grep patterns):
- `X endpoints` across `Y controllers`
- `X tests` (and breakdown: Python + C# Core + C# Api + C# Infra)
- `X tables + Y views`
- `X CLI commands` across `Y groups`
- Phase status references
- File path references (if new files were added)
- Key conventions section accuracy

### `C:/Users/jerem/.claude/projects/c--git-fedProspect/memory/MEMORY.md`

Values to check:
- "Current Counts" section -- endpoint count, table count, test counts, CLI command count
- Controller count
- Phase references

### `c:/git/fedProspect/thesolution/MASTER-PLAN.md`

Values to check:
- Phase statuses (mark completed phases as `[x] COMPLETE (date)`)
- Deliverable summaries with counts
- New phase entries if phases were added

### `c:/git/fedProspect/thesolution/QUICKSTART.md`

Values to check:
- Prerequisites and version numbers
- Setup instructions accuracy
- CLI command examples

### Phase-Specific Docs

If `$ARGUMENTS` mentions a phase number, also update:
- `c:/git/fedProspect/thesolution/phases/{phase-file}.md` -- mark completed tasks

## Step 3: Apply Updates

For each stale value found, update the file with the correct value. Use the Edit tool to make surgical replacements of old values with new values.

Show a summary of all changes made in this format:

```
Documentation Audit Results:
- CLAUDE.md: Updated test count 1,310 -> 1,345
- CLAUDE.md: Updated endpoint count 59 -> 61
- MEMORY.md: Updated test count to match
- MASTER-PLAN.md: No changes needed
- QUICKSTART.md: No changes needed
```

## Step 4: Audit Skills & Agents

Scan `.claude/skills/` for stale values. These skills embed counts or paths that drift:

### `run-tests/SKILL.md`
- Python test count (currently 738)
- C# Core test count (currently 313)
- C# Api test count (currently 236)
- C# Infra test count (currently 23)
- Total test count (currently 1,310)

### `add-endpoint/SKILL.md` and `references/endpoint-checklist.md`
- DI registration line numbers in Program.cs (currently ~124-137)
- Controller list if controllers were added/removed

### `check-health/SKILL.md`
- MySQL credentials (read from `thesolution/credentials.yml`)
- File paths if project structure changed

### Agent files (`.claude/agents/*.md`)
- Generally stable (pattern-based), but review if conventions changed significantly

## Step 5: Verify

After updating, grep all doc files AND skill files for the OLD values to ensure none were missed. If any old values remain, update those occurrences as well.

For the condensed version, see [references/doc-audit-checklist.md](references/doc-audit-checklist.md).
