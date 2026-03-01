# Phase 4: Sales/Prospecting Pipeline

**Status**: [x] COMPLETE (2026-02-22)
**Dependencies**: Phase 3 (Opportunities Pipeline) complete
**Deliverable**: Team can assign, track, score, and manage contract opportunities through a pipeline

---

## Implementation

**Business logic**: `fed_prospector/etl/prospect_manager.py` - `ProspectManager` class
**CLI commands**: 12 new commands added to `fed_prospector/main.py`

---

## Tasks

### 4.1 User Management
- [x] Implement user management CLI commands:
  - [x] `add-user --username --name --email --role`
  - [x] `list-users [--all]`
  - [x] `deactivate_user()` method (available in ProspectManager, no dedicated CLI - use via code)

### 4.2 Prospect Tracking
- [x] Implement prospect creation:
  - [x] `create-prospect --notice-id --assign-to --priority [--notes]`
  - [x] Validate notice_id exists in `opportunity` table
  - [x] Validate assigned_to exists in `app_user` table
  - [x] Set initial status to 'NEW'
- [x] Implement prospect status updates:
  - [x] `update-prospect --id --status --user [--notes]`
  - [x] Status flow: NEW -> REVIEWING -> PURSUING -> BID_SUBMITTED -> WON/LOST
  - [x] Alternative: NEW -> REVIEWING -> DECLINED/NO_BID
  - [x] Auto-create status change note in `prospect_note`
- [x] Implement prospect reassignment:
  - [x] `reassign-prospect --id --to --by [--notes]`
  - [x] Auto-create ASSIGNMENT note
- [x] Implement prospect listing:
  - [x] `list-prospects [--status] [--assigned-to] [--priority] [--open-only]`
  - [x] Show: opportunity title, deadline, days until due, status, assigned to
  - [x] Sort by deadline (most urgent first)
- [x] Implement prospect detail view:
  - [x] `show-prospect --id` displays full prospect + opportunity + notes + team

### 4.3 Prospect Notes & Activity
- [x] Implement note creation:
  - [x] `add-note --prospect-id --user --type --text`
  - [x] Note types: COMMENT, STATUS_CHANGE, ASSIGNMENT, DECISION, REVIEW, MEETING
- [x] Implement note listing:
  - [x] `show-prospect --id` displays full prospect detail + all notes in chronological order
- [x] Auto-log status changes and reassignments as notes

### 4.4 Go/No-Go Scoring
- [x] Design scoring framework (0-40 scale):
  - [x] Set-aside favorability: WOSB/EDWOSB=10, 8A/8AN=8, SBA/SBP=5, none=0
  - [x] Time remaining: >30d=10, 15-30=7, 7-14=4, <7=1, past=0
  - [x] NAICS match: checks entity_naics for WOSB entities with matching code (10 or 0)
  - [x] Award value bracket: $1M+=10, $500K+=8, $100K+=6, $50K+=4, below=2, unknown=3
- [x] Implement `go_no_go_score` calculation via `calculate_score()` method
- [x] Updates `go_no_go_score` on prospect record automatically

### 4.5 Teaming Partner Tracking
- [x] Implement `prospect_team_member` management:
  - [x] `add-team-member --prospect-id --uei --role [--notes]`
  - [x] Roles: PRIME, SUB, MENTOR, JV_PARTNER
  - [x] Validates UEI exists in `entity` table (warns if not found, adds anyway)
- [x] Display team members when showing prospect detail (in `show-prospect`)

### 4.6 Saved Searches
- [x] Implement saved search creation:
  - [x] `save-search --name --user --set-asides --naics --states --min-value --max-value --types --days-back --open-only`
  - [x] Store filter criteria as JSON in `saved_search.filter_criteria`
- [x] Implement saved search execution:
  - [x] `run-search --name` or `run-search --id`
  - [x] Query `opportunity` table with stored filters (dynamic SQL WHERE)
  - [x] Show count of new results since last run
  - [x] Update `last_run_at` and `last_new_results`
- [x] Implement saved search listing:
  - [x] `list-searches [--user]`
- [ ] Implement notification flag for future alerting:
  - [ ] `saved_search.notification_enabled` = 'Y' means alert when new results found (Phase 6)

### 4.7 Pipeline Dashboard (CLI)
- [x] Implement `dashboard` command showing:
  - [x] Open prospects by status (with bar chart)
  - [x] Prospects due this week (deadline within 7 days)
  - [x] Workload by assignee
  - [x] Win/loss statistics with win rate
  - [x] Saved searches with last run and new result counts

---

## CLI Command Reference

| Command | Description |
|---------|-------------|
| `add-user` | Add a team member (`--username`, `--name`, `--email`, `--role`) |
| `list-users` | List team members (`--all` for inactive too) |
| `create-prospect` | Create prospect (`--notice-id`, `--assign-to`, `--priority`, `--notes`) |
| `update-prospect` | Update status (`--id`, `--status`, `--user`, `--notes`) |
| `reassign-prospect` | Reassign (`--id`, `--to`, `--by`, `--notes`) |
| `list-prospects` | List with filters (`--status`, `--assigned-to`, `--priority`, `--open-only`) |
| `show-prospect` | Full detail view (`--id`) |
| `add-note` | Add note (`--prospect-id`, `--user`, `--type`, `--text`) |
| `add-team-member` | Add partner (`--prospect-id`, `--uei`, `--role`, `--notes`) |
| `save-search` | Save filter set (`--name`, `--user`, filter options) |
| `run-search` | Execute saved search (`--name` or `--id`) |
| `list-searches` | List saved searches (`--user`) |
| `dashboard` | Pipeline dashboard overview |

---

## Acceptance Criteria

1. [x] Users can be created and managed
2. [x] Prospects can be created from any opportunity in the database
3. [x] Prospect status flows correctly through the pipeline
4. [x] All status changes and notes are logged with timestamps and user attribution
5. [x] Go/No-Go scoring produces a consistent numeric score (0-40 scale)
6. [x] Saved searches return filtered results matching stored criteria
7. [x] Pipeline dashboard shows accurate current state
8. [x] Teaming partners can be associated with prospects

---

## Prospect Status Flow

```
                    +---> DECLINED
                    |
    NEW ---> REVIEWING ---> PURSUING ---> BID_SUBMITTED ---> WON
                    |                                    |
                    +---> NO_BID                         +---> LOST
```

---

## Saved Search Example

```json
{
    "name": "WOSB IT Services - Midwest",
    "filter_criteria": {
        "set_aside_codes": ["WOSB", "EDWOSB", "WOSBSS", "EDWOSBSS"],
        "naics_codes": ["541511", "541512", "541519", "541611"],
        "states": ["WI", "IL", "MN", "MI", "IN", "OH", "IA"],
        "min_award_amount": 50000,
        "max_award_amount": 10000000,
        "types": ["o", "k", "p"],
        "open_only": true
    }
}
```

## Known Issues

- Notification alerting for saved searches deferred to Phase 6 (Automation)
- `win_probability` is manual only (no auto-calculation) - user sets directly on prospect record
- `deactivate-user` has no dedicated CLI command; use `ProspectManager().deactivate_user(username)` from code
