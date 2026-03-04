# Documentation Audit Checklist

## Files to Audit

| File | Key Values |
|------|-----------|
| `CLAUDE.md` | endpoints, controllers, tables, views, CLI commands, conventions, file paths |
| `MEMORY.md` (at `C:/Users/jerem/.claude/projects/c--git-fedProspect/memory/`) | structural counts, environment, workflow prefs |
| `thesolution/MASTER-PLAN.md` | phase statuses, deliverable summaries |
| `thesolution/QUICKSTART.md` | prerequisites, setup instructions |
| `thesolution/phases/*.md` | task checkboxes, completion status |

## Structural Count Patterns to Grep

- `\d+ endpoints`
- `\d+ controllers`
- `\d+ tables`
- `\d+ views`
- `\d+ CLI commands`
- `\d+ groups`

## NOT Tracked in Docs

- Test counts (test runners report these)
- Source file line numbers (drift constantly)

## Skills to Check

| Skill File | Stale-Prone Values |
|---|---|
| `add-endpoint/SKILL.md` | DI registration line numbers, controller list |
| `check-health/SKILL.md` | MySQL credentials, file paths |
