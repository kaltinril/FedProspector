---
name: update-docs
description: "Update project documentation after changes: phase status, conventions, file paths. Scoped to what actually changed. Usage: /update-docs [description of what changed]"
argument-hint: "[description of what changed]"
---

# Update Documentation Skill

Update project documentation after code changes. Focus on what actually changed — don't audit everything every time.

## Arguments

`$ARGUMENTS` = description of what changed. This determines which docs to update.

## What to Update (and When)

| Change Type | Files to Update |
|-------------|----------------|
| Phase completed | MASTER-PLAN.md (mark phase done), phase file (mark tasks done) |
| New endpoints/controllers added | CLAUDE.md (endpoint count, controller list, file references) |
| New tables/views added | CLAUDE.md (table/view count) |
| New CLI commands added | CLAUDE.md (CLI command count) |
| New conventions or patterns | CLAUDE.md (Key Conventions section) |
| New files/folders added | CLAUDE.md (Project File References table) |
| Credential changes | QUICKSTART.md, credentials.yml |
| Skills affected | `.claude/skills/` (file paths, DI line numbers) |
| MEMORY.md | Only update for environment changes, new workflow preferences, or structural count changes (endpoints, tables, CLI commands) |

## What NOT to Track in Docs

- **Test counts** — test runners report these. Don't embed counts in any doc.
- **Line numbers** in source files — they drift constantly.
- **Historical phase counts** — completed phase docs are frozen records.

## Docs Reference

| File | Purpose | Key Values |
|------|---------|-----------|
| `CLAUDE.md` | Agent instructions | endpoints, controllers, tables, views, CLI commands, conventions, file paths |
| `MEMORY.md` | Cross-session memory (auto-loaded into context) | structural counts, environment, workflow prefs |
| `thesolution/MASTER-PLAN.md` | Phase tracking | phase statuses, deliverable summaries |
| `thesolution/QUICKSTART.md` | Setup guide | prerequisites, setup instructions |
| `thesolution/phases/*.md` | Phase details | task checkboxes |

## Skills to Check

Only check these if changes affect their embedded values:

| Skill | What Drifts |
|-------|-------------|
| `add-endpoint/SKILL.md` | Controller list, DI registration block |
| `check-health/SKILL.md` | MySQL credentials, file paths |

## Process

1. Read `$ARGUMENTS` to understand what changed
2. Determine which docs are affected (use table above)
3. Read only the affected files
4. Make surgical edits
5. Show a summary of changes made
