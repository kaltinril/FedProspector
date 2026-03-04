---
name: add-phase
description: "Create a new phase plan document or mark an existing phase as complete. Usage: /add-phase create <number> <name> OR /add-phase complete <number>"
argument-hint: "create <number> <name> | complete <number>"
disable-model-invocation: true
context: fork
agent: coder
---

**Arguments**:
- `create <number> <name>` -- create new phase doc and add to MASTER-PLAN
- `complete <number>` -- mark phase as done in phase doc and MASTER-PLAN

## Create Mode

1. **Create phase file** at `c:/git/fedProspect/thesolution/phases/{NUMBER}-{NAME}.md`

Use this template:
```markdown
# Phase {NUMBER}: {NAME}

**Status**: NOT STARTED
**Dependencies**: [Phase X (Name)] -- determine from MASTER-PLAN context
**Deliverable**: [One sentence -- ask user if not obvious from name]

---

## Overview

[2-3 paragraphs describing what this phase accomplishes and why]

## Tech Stack (if applicable)

| Layer | Choice | Why |
|-------|--------|-----|
| | | |

## Project Structure (if applicable)

```
folder/
  subfolder/
    files
```

---

## Tasks

### {NUMBER}.1 [First Task Group]
- [ ] Subtask 1
- [ ] Subtask 2

### {NUMBER}.2 [Second Task Group]
- [ ] Subtask 1

---

## Self-Service Commands

```bash
# Commands to run/verify this phase's work
```

## Verification

- [ ] Criterion 1
- [ ] Criterion 2

---

## Known Issues

[Document any issues discovered during implementation]
```

2. **Add entry to MASTER-PLAN** at `c:/git/fedProspect/thesolution/MASTER-PLAN.md`

Add in the Phase Roadmap section, maintaining numerical order:
```markdown
### Phase {NUMBER}: {NAME}
**Status**: [ ] NOT STARTED
**File**: [phases/{NUMBER}-{NAME}.md](phases/{NUMBER}-{NAME}.md)
**Dependencies**: Phase X (Name)

- [ ] Deliverable summary
```

## Complete Mode

1. **Update phase file**: Change status to `COMPLETE ({today's date in YYYY-MM-DD})`, mark all task checkboxes as `[x]`

2. **Update MASTER-PLAN entry**: Change `[ ] NOT STARTED` or `[ ] IN PROGRESS` to `[x] COMPLETE ({date})`, mark deliverable checkboxes as `[x]`

3. **Update counts** in CLAUDE.md and MEMORY.md if the phase affected:
   - Test counts
   - Endpoint/controller counts
   - Table/view counts
   - CLI command counts

## Reference Files

- Existing phases: `c:/git/fedProspect/thesolution/phases/` (read any for format reference)
- Master plan: `c:/git/fedProspect/thesolution/MASTER-PLAN.md`
