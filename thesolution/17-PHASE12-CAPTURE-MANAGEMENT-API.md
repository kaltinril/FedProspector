# Phase 12: Capture Management API (CRUD Endpoints)

**Status**: PLANNING
**Dependencies**: Phase 11 (Read Endpoints) complete
**Deliverable**: All write/CRUD endpoints for prospects, proposals, notes, team members
**Repository**: `api/` (monorepo -- same repo as Python ETL)

---

## Overview

Implement all create, update, and delete endpoints that power the capture management workflow. This phase replicates the business logic currently in Python's `ProspectManager` class and adds new proposal management capabilities.

**Total endpoints this phase: 10 write endpoints**

---

## Tasks

### 12.1 ProspectsController (CRUD)

#### `POST /api/v1/prospects` -- Create prospect from opportunity
- [ ] Validate: `noticeId` exists in opportunity table, not already tracked
- [ ] Set initial status = `NEW`, auto-assign if user specified
- [ ] Auto-calculate initial Go/No-Go score
- [ ] Auto-create `STATUS_CHANGE` note: "Prospect created with status NEW, priority {priority}."
- [ ] Log activity: "Created prospect from opportunity {noticeId}"

Request:
```json
{
  "noticeId": "abc123",
  "assignedTo": 1,
  "captureManagerId": 2,
  "priority": "HIGH",
  "notes": "Initial assessment notes"
}
```

Response: 201 Created with full prospect detail

Validation rules (from Python `create_prospect()`):
- `priority` must be one of: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`
- `noticeId` must exist in `opportunity` table (SELECT notice_id FROM opportunity WHERE notice_id = ?)
- `assignedTo` must reference an active `app_user` (is_active = 'Y')
- If `notes` provided, append to the auto-created STATUS_CHANGE note text

> **Contracting Officer association**: When creating or editing a prospect, users can associate a Contracting Officer. The API matches on email (case-insensitive) or name + office to reuse existing `contracting_officer` records, avoiding duplicates. New CO records are created automatically if no match is found. Note that COs are also auto-populated from the SAM.gov Opportunity API during ETL loads (via the `opportunity_poc` junction table), so manual entry here is only needed when the API data is incomplete or missing.

#### `GET /api/v1/prospects` -- List with filters
- [ ] Filters: `status`, `assignedTo`, `captureManagerId`, `priority`, `naics`, `setAside`, `openOnly` (exclude terminal statuses)
- [ ] Sort by: `responseDeadline`, `estimatedValue`, `goNoGoScore`, `createdAt`
- [ ] Pagination standard
- [ ] JOIN to opportunity for title, deadline, set-aside, NAICS, department, active flag
- [ ] JOIN to app_user for assigned username/display_name
- [ ] `openOnly=true` excludes statuses: WON, LOST, DECLINED, NO_BID

#### `GET /api/v1/prospects/{id}` -- Full prospect detail
- [ ] Full prospect record with all columns
- [ ] Nested: `notes[]`, `teamMembers[]`, `proposal` (if exists), `opportunity` detail
- [ ] Include current Go/No-Go score breakdown
- [ ] Notes ordered by created_at ASC
- [ ] Team members joined to entity table for legal_business_name

Response:
```json
{
  "prospect": {
    "prospectId": 1,
    "noticeId": "abc123",
    "status": "PURSUING",
    "priority": "HIGH",
    "goNoGoScore": 28,
    "winProbability": 0.70,
    "estimatedValue": 500000.00,
    "estimatedGrossMarginPct": 25.00,
    "captureManager": { "userId": 2, "displayName": "Jane Smith" },
    "assignedTo": { "userId": 1, "displayName": "John Doe" },
    "createdAt": "2026-02-28T10:00:00Z",
    "updatedAt": "2026-02-28T12:00:00Z"
  },
  "opportunity": {
    "title": "IT Support Services",
    "solicitationNumber": "W91234-26-R-0001",
    "departmentName": "Department of Defense",
    "subTier": "Army",
    "office": "ACC-APG",
    "postedDate": "2026-02-01",
    "responseDeadline": "2026-04-01T14:00:00Z",
    "type": "o",
    "setAsideCode": "WOSB",
    "setAsideDescription": "Women-Owned Small Business",
    "naicsCode": "541512",
    "popState": "MD",
    "popZip": "21005",
    "popCountry": "USA",
    "active": "Y",
    "awardAmount": null,
    "link": "https://sam.gov/opp/abc123/view"
  },
  "notes": [
    {
      "noteId": 1,
      "noteType": "STATUS_CHANGE",
      "noteText": "Prospect created with status NEW, priority HIGH.",
      "createdBy": { "username": "jdoe", "displayName": "John Doe" },
      "createdAt": "2026-02-28T10:00:00Z"
    },
    {
      "noteId": 2,
      "noteType": "MEETING",
      "noteText": "Met with contracting officer. They confirmed WOSB set-aside.",
      "createdBy": { "username": "jsmith", "displayName": "Jane Smith" },
      "createdAt": "2026-02-28T11:30:00Z"
    }
  ],
  "teamMembers": [
    {
      "id": 1,
      "ueiSam": "ABC123DEF456",
      "entityName": "Acme Corp",
      "role": "SUB",
      "notes": "Handles network infrastructure",
      "proposedHourlyRate": 150.00,
      "commitmentPct": 50.00
    }
  ],
  "proposal": null,
  "scoreBreakdown": {
    "setAside": { "score": 10, "max": 10, "detail": "WOSB -> 10 pts" },
    "timeRemaining": { "score": 10, "max": 10, "detail": "32 days left -> 10 pts" },
    "naicsMatch": { "score": 10, "max": 10, "detail": "NAICS 541512: MATCH -> 10 pts" },
    "awardValue": { "score": 3, "max": 10, "detail": "Unknown value -> 3 pts" },
    "total": 33,
    "maxTotal": 40,
    "percentage": 82.5
  }
}
```

#### `PATCH /api/v1/prospects/{id}/status` -- Status transition
- [ ] **CRITICAL**: Replicate exact status flow from Python ProspectManager

Copy the STATUS_FLOW map from `prospect_manager.py` and implement verbatim:
```csharp
// STATUS_FLOW -- replicated from Python ProspectManager (prospect_manager.py lines 27-33)
private static readonly Dictionary<string, string[]> StatusFlow = new()
{
    ["NEW"] = new[] { "REVIEWING", "DECLINED" },
    ["REVIEWING"] = new[] { "PURSUING", "DECLINED", "NO_BID" },
    ["PURSUING"] = new[] { "BID_SUBMITTED", "DECLINED" },
    ["BID_SUBMITTED"] = new[] { "WON", "LOST" }
};

private static readonly HashSet<string> TerminalStatuses = new()
{
    "WON", "LOST", "DECLINED", "NO_BID"
};
```

Rules (from Python `update_status()`, lines 235-321):
1. Fetch current status; return 404 if prospect not found
2. If current status is in TerminalStatuses, return 400: "Prospect {id} is in terminal status '{current}' and cannot be updated"
3. Look up allowed transitions from StatusFlow; if new status not in list, return 400: "Invalid status transition: {current} -> {new}. Allowed transitions: {allowed}"
4. On any terminal status transition: set `outcome = newStatus`, `outcome_date = NOW()`, `outcome_notes = notes` (if provided)
5. On BID_SUBMITTED transition: set `bid_submitted_date = NOW()`
6. Auto-create `STATUS_CHANGE` note: "Status changed: {old} -> {new}. {notes}"
7. Log activity with old/new values

Request:
```json
{
  "newStatus": "PURSUING",
  "notes": "Decision: proceed with bid preparation"
}
```

Response: 200 OK with updated prospect detail

#### `PATCH /api/v1/prospects/{id}/reassign` -- Reassign prospect
- [ ] Validate new assignee exists and is active
- [ ] Auto-create `ASSIGNMENT` note: "Reassigned from {oldUsername} to {newUsername}."
- [ ] Log activity

Request:
```json
{
  "newAssignedTo": 3,
  "notes": "Reassigning due to workload balancing"
}
```

#### `POST /api/v1/prospects/{id}/notes` -- Add capture note
- [ ] Validate note_type against allowed list: `COMMENT`, `ASSIGNMENT`, `DECISION`, `REVIEW`, `MEETING`
- [ ] `STATUS_CHANGE` notes are auto-generated by the system during status transitions and cannot be created manually.
- [ ] (Extended types also accepted for API flexibility: `PHONE_CALL`, `EMAIL`)
- [ ] Link to current authenticated user
- [ ] Validate prospect exists; return 404 if not found
- [ ] Log activity

Request:
```json
{
  "noteType": "MEETING",
  "noteText": "Met with contracting officer. They confirmed WOSB set-aside."
}
```

Response: 201 Created with note detail

#### `POST /api/v1/prospects/{id}/team-members` -- Add team member
- [ ] `ueiSam` links to entity table; warn (but allow) if UEI not found
- [ ] Role must be one of: `PRIME`, `SUB`, `MENTOR`, `JV_PARTNER`
- [ ] Validate prospect exists; return 404 if not found
- [ ] Log activity

Request:
```json
{
  "ueiSam": "ABC123DEF456",
  "role": "SUB",
  "notes": "Handles network infrastructure"
}
```

Response: 201 Created with team member detail (including entity name if found)

#### `DELETE /api/v1/prospects/{id}/team-members/{memberId}` -- Remove team member
- [ ] Hard delete (team member records are lightweight, no history needed)
- [ ] Validate prospect and member exist; return 404 if not found
- [ ] Log activity

---

### 12.2 Go/No-Go Scoring

- [ ] **CRITICAL**: Replicate exact scoring from Python ProspectManager `calculate_score()` (lines 899-1048)

Scoring criteria (0-40 scale, 4 criteria at 0-10 each):

#### Criterion 1: Set-aside favorability (0-10)

Exact mapping from `prospect_manager.py` lines 940-947:
```python
sa_scores = {
    "WOSB": 10, "EDWOSB": 10, "WOSBSS": 10, "EDWOSBSS": 10,
    "8A": 8, "8AN": 8,
    "SBA": 5, "SBP": 5,
    "HZC": 5, "HZS": 5,
    "SDVOSBC": 5, "SDVOSBS": 5,
}
# Any code not in this map = 0
```

C# implementation:
```csharp
private static readonly Dictionary<string, int> SetAsideScores = new(StringComparer.OrdinalIgnoreCase)
{
    ["WOSB"] = 10, ["EDWOSB"] = 10, ["WOSBSS"] = 10, ["EDWOSBSS"] = 10,
    ["8A"] = 8, ["8AN"] = 8,
    ["SBA"] = 5, ["SBP"] = 5,
    ["HZC"] = 5, ["HZS"] = 5,
    ["SDVOSBC"] = 5, ["SDVOSBS"] = 5,
};
// Lookup: SetAsideScores.GetValueOrDefault(saCode?.ToUpper() ?? "", 0)
```

#### Criterion 2: Time remaining until deadline (0-10)

From `prospect_manager.py` lines 955-972:
```
> 30 days  = 10
15-30 days = 7
7-14 days  = 4
< 7 days   = 1
Past due   = 0
No deadline (null) = 5 (neutral)
```

#### Criterion 3: NAICS match (0 or 10)

From `prospect_manager.py` lines 981-994. Checks if any entity in our database that has WOSB-related business type codes also has this NAICS code registered:
```sql
SELECT COUNT(*) AS cnt FROM entity_naics en
JOIN entity_business_type ebt ON en.uei_sam = ebt.uei_sam
WHERE en.naics_code = ? AND ebt.business_type_code IN ('2X', '8W', 'A2')
```
- Business type codes: `2X` (Woman Owned), `8W` (Woman Owned Small Business), `A2` (EDWOSB)
- If count > 0: score = 10 (our entity has this NAICS and is WOSB-eligible)
- If count = 0 or NAICS is null: score = 0

#### Criterion 4: Award value bracket (0-10)

From `prospect_manager.py` lines 1002-1017. Uses `award_amount` from opportunity, falls back to `estimated_value` from prospect:
```
>= $1,000,000 = 10
>= $500,000   = 8
>= $100,000   = 6
>= $50,000    = 4
< $50,000     = 2
Unknown/null  = 3 (neutral-low)
```

#### Scoring endpoints
- [ ] Auto-recalculate on prospect create and status change
- [ ] Score stored in `prospect.go_no_go_score` column
- [ ] Expose score breakdown in prospect detail endpoint (see 12.1 response example)
- [ ] `POST /api/v1/prospects/{id}/recalculate-score` -- manual recalculation trigger

Response from recalculate:
```json
{
  "prospectId": 1,
  "totalScore": 33,
  "maxScore": 40,
  "percentage": 82.5,
  "breakdown": {
    "setAside": { "score": 10, "max": 10, "detail": "WOSB -> 10 pts" },
    "timeRemaining": { "score": 10, "max": 10, "detail": "32 days left -> 10 pts" },
    "naicsMatch": { "score": 10, "max": 10, "detail": "NAICS 541512: MATCH -> 10 pts" },
    "awardValue": { "score": 3, "max": 10, "detail": "Unknown value -> 3 pts" }
  }
}
```

---

### 12.3 ProposalsController

#### `POST /api/v1/proposals` -- Create proposal for prospect
- [ ] Enforce 1:1 relationship (UNIQUE KEY on prospect_id)
- [ ] Set initial status = DRAFT
- [ ] Auto-create default milestones (configurable list):
  - Draft Due
  - Internal Review
  - Final Submission
  - Q&A Period
  - Award Decision
- [ ] Log activity

Request:
```json
{
  "prospectId": 1,
  "dueDate": "2026-04-15",
  "proposalOwnerId": 2,
  "internalCostEstimate": 350000.00,
  "proposedPrice": 500000.00
}
```

Response: 201 Created with full proposal detail including auto-created milestones

#### `PATCH /api/v1/proposals/{id}` -- Update proposal
- [ ] Update status, pricing, dates, document count
- [ ] Proposal status flow:
  ```
  DRAFT -> IN_REVIEW -> SUBMITTED -> UNDER_EVALUATION -> AWARDED | NOT_AWARDED
  ```

  Formal transition map (mirrors the prospect STATUS_FLOW pattern):
  ```csharp
  // PROPOSAL_STATUS_FLOW -- valid transitions for proposal status
  private static readonly Dictionary<string, string[]> ProposalStatusFlow = new()
  {
      ["DRAFT"] = new[] { "IN_REVIEW", "CANCELLED" },
      ["IN_REVIEW"] = new[] { "SUBMITTED", "DRAFT", "CANCELLED" },
      ["SUBMITTED"] = new[] { "UNDER_EVALUATION", "CANCELLED" },
      ["UNDER_EVALUATION"] = new[] { "AWARDED", "NOT_AWARDED" },
  };

  private static readonly HashSet<string> TerminalProposalStatuses = new()
  {
      "AWARDED", "NOT_AWARDED", "CANCELLED"
  };
  ```

- [ ] Sync `proposal_status` to `prospect.proposal_status` for quick filtering
- [ ] On SUBMITTED: auto-set `submitted_date = NOW()`
- [ ] On AWARDED: auto-transition prospect status to WON (using StatusFlow validation)
- [ ] On NOT_AWARDED: auto-transition prospect status to LOST (using StatusFlow validation)

> **Prerequisite**: A proposal can only advance to `SUBMITTED` if the parent prospect is at `BID_SUBMITTED` status. If the prospect is not yet at `BID_SUBMITTED`, the API returns 409 Conflict with a message indicating the prospect status must be advanced first.

- [ ] Log activity

Request:
```json
{
  "status": "SUBMITTED",
  "proposedPrice": 485000.00,
  "notes": "Final price adjusted after internal review"
}
```

#### `POST /api/v1/proposals/{id}/documents` -- Upload document metadata
- [ ] Create `proposal_document` record
- [ ] Increment `proposal.document_count`
- [ ] File storage handled by C# API (filesystem or blob storage -- not in MySQL)
- [ ] MySQL stores metadata only: filename, content type, size, upload timestamp

Request:
```json
{
  "fileName": "Technical_Volume.pdf",
  "contentType": "application/pdf",
  "fileSizeBytes": 2048576,
  "documentType": "RESPONSE"
}
```

Response: 201 Created with document metadata and storage URL

#### `GET /api/v1/proposals/{id}/milestones` -- List milestones
- [ ] All milestones for this proposal
- [ ] Sort by planned_date ASC

#### `PATCH /api/v1/proposals/{id}/milestones/{milestoneId}` -- Update milestone
- [ ] Update actual_date, status, notes
- [ ] Log activity

Request:
```json
{
  "actualDate": "2026-04-10",
  "status": "COMPLETED",
  "notes": "Draft completed 5 days early"
}
```

---

### 12.4 Activity Logging

- [ ] All write operations create `activity_log` records automatically
- [ ] Implement as a service called from each controller action (or middleware)
- [ ] Action types:
  - `CREATE_PROSPECT`
  - `UPDATE_STATUS`
  - `REASSIGN_PROSPECT`
  - `ADD_NOTE`
  - `ADD_TEAM_MEMBER`
  - `REMOVE_TEAM_MEMBER`
  - `CREATE_PROPOSAL`
  - `UPDATE_PROPOSAL`
  - `UPLOAD_DOCUMENT`
  - `UPDATE_MILESTONE`
  - `RECALCULATE_SCORE`
- [ ] Include `old_value` / `new_value` for status changes (JSON strings)
- [ ] Include IP address from `HttpContext.Connection.RemoteIpAddress`
- [ ] Include authenticated user ID from JWT claims

---

## Acceptance Criteria

1. [ ] Prospect CRUD: create, list, detail, status transition all work
2. [ ] Status flow enforced: invalid transitions return 400 with explanation message matching Python format
3. [ ] Terminal statuses (WON, LOST, DECLINED, NO_BID) set outcome, outcome_date, outcome_notes automatically
4. [ ] BID_SUBMITTED status sets bid_submitted_date automatically
5. [ ] Go/No-Go scoring matches Python output for same opportunity data (all 4 criteria, 0-40 scale)
6. [ ] Score breakdown visible in prospect detail response
7. [ ] NAICS match scoring queries entity_naics + entity_business_type with codes 2X, 8W, A2
8. [ ] Proposal lifecycle: DRAFT -> IN_REVIEW -> SUBMITTED -> UNDER_EVALUATION -> AWARDED/NOT_AWARDED works
9. [ ] Proposal-Prospect sync: AWARDED auto-transitions prospect to WON, NOT_AWARDED to LOST
10. [ ] Document upload creates metadata record and increments document_count
11. [ ] Milestones auto-created on proposal creation, individually updateable
12. [ ] Activity log records created for all write operations with old/new values
13. [ ] All endpoints require authentication (JWT Bearer)
14. [ ] Swagger shows request/response examples for all endpoints
15. [ ] Note types validated against allowed list (COMMENT, ASSIGNMENT, DECISION, REVIEW, MEETING); STATUS_CHANGE is system-only
16. [ ] Team member roles validated against allowed list (PRIME, SUB, MENTOR, JV_PARTNER)
17. [ ] Priority validated against allowed list (LOW, MEDIUM, HIGH, CRITICAL)

---

## Business Logic Reference

The C# implementation must produce identical results for identical inputs. Below are the full Python methods from `prospect_manager.py` that serve as the authoritative reference.

### `create_prospect()` -- Validation and defaults (lines 174-233)

```python
def create_prospect(self, notice_id, assigned_to_username, priority="MEDIUM", notes=None):
    if priority not in self.PRIORITY_LEVELS:
        raise ValueError(
            f"Invalid priority '{priority}'. Must be one of: {', '.join(self.PRIORITY_LEVELS)}"
        )

    conn = get_connection()
    cursor = conn.cursor()
    try:
        self._validate_notice_id(cursor, notice_id)
        user_id = self._get_user_id(cursor, assigned_to_username)

        cursor.execute(
            "INSERT INTO prospect (notice_id, assigned_to, status, priority) "
            "VALUES (%s, %s, 'NEW', %s)",
            (notice_id, user_id, priority),
        )
        prospect_id = cursor.lastrowid

        # Auto-create STATUS_CHANGE note
        note_text = f"Prospect created with status NEW, priority {priority}."
        if notes:
            note_text += f" {notes}"
        cursor.execute(
            "INSERT INTO prospect_note (prospect_id, user_id, note_type, note_text) "
            "VALUES (%s, %s, 'STATUS_CHANGE', %s)",
            (prospect_id, user_id, note_text),
        )

        conn.commit()
        return prospect_id
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()
```

### `update_status()` -- Status flow validation and transition (lines 235-321)

```python
def update_status(self, prospect_id, new_status, username, notes=None):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT prospect_id, status FROM prospect WHERE prospect_id = %s",
            (prospect_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Prospect {prospect_id} not found")

        current_status = row["status"]
        if current_status in self.TERMINAL_STATUSES:
            raise ValueError(
                f"Prospect {prospect_id} is in terminal status '{current_status}' "
                f"and cannot be updated"
            )

        allowed = self.STATUS_FLOW.get(current_status, [])
        if new_status not in allowed:
            raise ValueError(
                f"Invalid status transition: {current_status} -> {new_status}. "
                f"Allowed transitions: {', '.join(allowed)}"
            )

        user_id = self._get_user_id(cursor, username)

        # Update the status
        update_fields = {"status": new_status}

        # Set outcome-related fields for terminal statuses
        if new_status in self.TERMINAL_STATUSES:
            update_fields["outcome"] = new_status
            update_fields["outcome_date"] = datetime.now().strftime("%Y-%m-%d")
            if notes:
                update_fields["outcome_notes"] = notes

        if new_status == "BID_SUBMITTED":
            update_fields["bid_submitted_date"] = datetime.now().strftime("%Y-%m-%d")

        set_clause = ", ".join(f"{k} = %s" for k in update_fields)
        values = list(update_fields.values()) + [prospect_id]
        cursor.execute(
            f"UPDATE prospect SET {set_clause} WHERE prospect_id = %s",
            values,
        )

        # Auto-create STATUS_CHANGE note
        note_text = f"Status changed: {current_status} -> {new_status}."
        if notes:
            note_text += f" {notes}"
        cursor.execute(
            "INSERT INTO prospect_note (prospect_id, user_id, note_type, note_text) "
            "VALUES (%s, %s, 'STATUS_CHANGE', %s)",
            (prospect_id, user_id, note_text),
        )

        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()
```

### `calculate_score()` -- Go/No-Go scoring with all 4 criteria (lines 899-1048)

```python
def calculate_score(self, prospect_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # Fetch prospect + opportunity data
        cursor.execute(
            "SELECT p.prospect_id, p.notice_id, p.estimated_value, "
            "  o.set_aside_code, o.naics_code, o.response_deadline, "
            "  o.award_amount "
            "FROM prospect p "
            "JOIN opportunity o ON p.notice_id = o.notice_id "
            "WHERE p.prospect_id = %s",
            (prospect_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Prospect {prospect_id} not found")

        breakdown = {}

        # 1. Set-aside favorability (0-10)
        sa_code = (row.get("set_aside_code") or "").upper()
        sa_scores = {
            "WOSB": 10, "EDWOSB": 10, "WOSBSS": 10, "EDWOSBSS": 10,
            "8A": 8, "8AN": 8,
            "SBA": 5, "SBP": 5,
            "HZC": 5, "HZS": 5,
            "SDVOSBC": 5, "SDVOSBS": 5,
        }
        set_aside_score = sa_scores.get(sa_code, 0)
        breakdown["set_aside"] = {
            "score": set_aside_score,
            "max": 10,
            "detail": f"{sa_code or 'none'} -> {set_aside_score} pts",
        }

        # 2. Time remaining (0-10)
        deadline = row.get("response_deadline")
        if deadline:
            if isinstance(deadline, str):
                deadline = datetime.strptime(deadline, "%Y-%m-%d %H:%M:%S")
            days_left = (deadline - datetime.now()).days
            if days_left < 0:
                time_score = 0
            elif days_left < 7:
                time_score = 1
            elif days_left < 14:
                time_score = 4
            elif days_left <= 30:
                time_score = 7
            else:
                time_score = 10
        else:
            days_left = None
            time_score = 5  # Unknown deadline, give neutral score

        breakdown["time_remaining"] = {
            "score": time_score,
            "max": 10,
            "detail": f"{days_left} days left -> {time_score} pts"
                      if days_left is not None
                      else "No deadline -> 5 pts",
        }

        # 3. NAICS match (0-10)
        naics_code = row.get("naics_code")
        naics_score = 0
        if naics_code:
            cursor.execute(
                "SELECT COUNT(*) AS cnt FROM entity_naics en "
                "JOIN entity_business_type ebt ON en.uei_sam = ebt.uei_sam "
                "WHERE en.naics_code = %s "
                "AND ebt.business_type_code IN ('2X', '8W', 'A2')",
                (naics_code,),
            )
            match_row = cursor.fetchone()
            if match_row and match_row["cnt"] > 0:
                naics_score = 10

        breakdown["naics_match"] = {
            "score": naics_score,
            "max": 10,
            "detail": f"NAICS {naics_code or 'none'}: "
                      f"{'MATCH' if naics_score > 0 else 'no match'} "
                      f"-> {naics_score} pts",
        }

        # 4. Award value (0-10)
        value = row.get("award_amount") or row.get("estimated_value")
        if value:
            value = float(value)
            if value >= 1_000_000:
                value_score = 10
            elif value >= 500_000:
                value_score = 8
            elif value >= 100_000:
                value_score = 6
            elif value >= 50_000:
                value_score = 4
            else:
                value_score = 2
        else:
            value_score = 3  # Unknown value, neutral-low

        breakdown["award_value"] = {
            "score": value_score,
            "max": 10,
            "detail": f"${value:,.0f} -> {value_score} pts"
                      if value
                      else f"Unknown value -> {value_score} pts",
        }

        # Total score
        total = set_aside_score + time_score + naics_score + value_score
        max_total = 40

        # Update prospect record
        cursor.execute(
            "UPDATE prospect SET go_no_go_score = %s WHERE prospect_id = %s",
            (total, prospect_id),
        )
        conn.commit()

        return {
            "prospect_id": prospect_id,
            "total_score": total,
            "max_score": max_total,
            "percentage": round((total / max_total) * 100, 1),
            "breakdown": breakdown,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()
```

### `get_dashboard_data()` -- All 6 dashboard sub-queries (lines 1054-1137)

```python
def get_dashboard_data(self):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        dashboard = {}

        # 1. Prospects by status
        cursor.execute(
            "SELECT status, COUNT(*) AS cnt FROM prospect "
            "GROUP BY status ORDER BY status"
        )
        dashboard["by_status"] = {
            row["status"]: row["cnt"] for row in cursor.fetchall()
        }

        # 2. Due this week (response_deadline within 7 days)
        cursor.execute(
            "SELECT p.prospect_id, p.status, p.priority, "
            "  o.title, o.response_deadline, o.set_aside_code, "
            "  u.username AS assigned_to "
            "FROM prospect p "
            "JOIN opportunity o ON p.notice_id = o.notice_id "
            "LEFT JOIN app_user u ON p.assigned_to = u.user_id "
            "WHERE p.status NOT IN ('WON', 'LOST', 'DECLINED', 'NO_BID') "
            "  AND o.response_deadline BETWEEN NOW() "
            "  AND DATE_ADD(NOW(), INTERVAL 7 DAY) "
            "ORDER BY o.response_deadline ASC"
        )
        dashboard["due_this_week"] = cursor.fetchall()

        # 3. By assignee
        cursor.execute(
            "SELECT u.username, u.display_name, COUNT(*) AS cnt "
            "FROM prospect p "
            "JOIN app_user u ON p.assigned_to = u.user_id "
            "WHERE p.status NOT IN ('WON', 'LOST', 'DECLINED', 'NO_BID') "
            "GROUP BY u.user_id, u.username, u.display_name "
            "ORDER BY cnt DESC"
        )
        dashboard["by_assignee"] = cursor.fetchall()

        # 4. Win/loss stats
        cursor.execute(
            "SELECT outcome, COUNT(*) AS cnt FROM prospect "
            "WHERE outcome IS NOT NULL "
            "GROUP BY outcome ORDER BY outcome"
        )
        dashboard["win_loss"] = {
            row["outcome"]: row["cnt"] for row in cursor.fetchall()
        }

        # 5. Saved searches
        cursor.execute(
            "SELECT s.search_id, s.search_name, s.last_run_at, "
            "  s.last_new_results, u.username "
            "FROM saved_search s "
            "JOIN app_user u ON s.user_id = u.user_id "
            "WHERE s.is_active = 'Y' "
            "ORDER BY s.search_name"
        )
        dashboard["saved_searches"] = cursor.fetchall()

        # Total open prospects
        cursor.execute(
            "SELECT COUNT(*) AS cnt FROM prospect "
            "WHERE status NOT IN ('WON', 'LOST', 'DECLINED', 'NO_BID')"
        )
        row = cursor.fetchone()
        dashboard["total_open"] = row["cnt"] if row else 0

        return dashboard
    finally:
        cursor.close()
        conn.close()
```

---

## Implementation Details

- **Architecture**: ASP.NET Core Web API controllers with service layer for business logic
- **Status Flow**: Replicated from Python `ProspectManager.STATUS_FLOW` dict -- must be identical
- **Scoring**: Replicated from Python `ProspectManager.calculate_score()` -- must produce identical scores for identical input data
- **Activity Logging**: Service-based (not middleware) to capture action-specific old/new values
- **Proposal Sync**: Proposal status changes that imply prospect outcomes (AWARDED/NOT_AWARDED) must auto-transition the prospect using the same StatusFlow validation
- **Validation Lists**: Priority (4 values), Note Types (5 user-selectable + STATUS_CHANGE system-only), Team Roles (4 values) -- all from Python ProspectManager class constants
