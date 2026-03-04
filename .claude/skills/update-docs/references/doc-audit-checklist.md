# Documentation Audit Checklist

## Files to Audit

| File | Key Values |
|------|-----------|
| `CLAUDE.md` | test counts, endpoints, controllers, tables, views, CLI commands, phase status |
| `MEMORY.md` (at `C:/Users/jerem/.claude/projects/c--git-fedProspect/memory/`) | Current Counts section |
| `thesolution/MASTER-PLAN.md` | phase statuses, deliverable summaries |
| `thesolution/QUICKSTART.md` | prerequisites, setup instructions |
| `thesolution/phases/*.md` | task checkboxes, completion status |

## Count Patterns to Grep

- `\d+ endpoints`
- `\d+ controllers`
- `\d+ tests`
- `\d+ Python`
- `\d+ C# Core`
- `\d+ C# Api`
- `\d+ C# Infra`
- `\d+ tables`
- `\d+ views`
- `\d+ CLI commands`
- `\d+ groups`

## Skills to Audit

| Skill File | Stale-Prone Values |
|---|---|
| `run-tests/SKILL.md` | test counts (738, 313, 236, 23, 1,310) |
| `add-endpoint/SKILL.md` | DI registration line numbers, controller list |
| `check-health/SKILL.md` | MySQL credentials, file paths |

## Verification

After updating, grep all doc files AND `.claude/skills/` for the OLD values to ensure none were missed.
