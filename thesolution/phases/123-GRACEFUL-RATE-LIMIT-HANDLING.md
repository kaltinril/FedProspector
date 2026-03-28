# Phase 123: Graceful Rate Limit Handling

**Status:** PLANNED
**Priority:** Medium — UX improvement, prevents wasted API calls
**Dependencies:** Phase 112 (Description Backfill), Phase 110Y (Request Poller)

---

## Summary

When the SAM.gov API key daily limit is reached, on-demand actions (like "Fetch Description from SAM.gov") fail with a generic 502 error. The user has no idea why it failed or what to do. This phase adds graceful handling: try the call, and if rate-limited, queue it for the poller to process after the daily reset.

This pattern applies to any on-demand SAM.gov API call, not just descriptions.

---

## Flow

1. User clicks "Fetch Description from SAM.gov" on the UI
2. C# API attempts the SAM.gov call directly
3. If successful: return description (existing behavior)
4. If 429 (rate limited):
   a. Insert a `data_load_request` with `request_type='DESCRIPTION_FETCH'`
   b. Return 202 Accepted with message: "Daily API limit reached — queued for automatic fetch tomorrow"
5. UI shows an info/blue snackbar with the queued message (not a red error)
6. Poller picks it up after the daily reset

---

## Task 1: C# API — Detect 429 and Queue

**Endpoint:** `POST /opportunities/{noticeId}/fetch-description`

- Catch `HttpRequestException` with 429 status from the SAM.gov call
- Insert `data_load_request` row: `request_type='DESCRIPTION_FETCH'`, `parameters={"notice_id": "..."}`
- Return 202 Accepted with body: `{ "queued": true, "message": "Daily API limit reached — queued for automatic fetch" }`

## Task 2: Demand Loader — DESCRIPTION_FETCH Handler

**File:** `fed_prospector/etl/demand_loader.py`

- New handler for `request_type='DESCRIPTION_FETCH'`
- Calls `fetch_description_text()` for the queued notice_id
- Saves result to `opportunity.description_text`
- Marks request COMPLETED or FAILED

## Task 3: Poller Rate Limit Awareness

**Problem:** If the poller tries to process `DESCRIPTION_FETCH` requests while the key is still maxed, it'll fail every one and mark them all as permanently FAILED.

**Solution options (research needed):**
- Track last 429 timestamp. Skip DESCRIPTION_FETCH requests until after the reset window (SAM.gov Key 2 resets at 4pm AKT / midnight UTC)
- Or: on 429 failure, set request status to `PENDING_RETRY` instead of `FAILED`, with a `retry_after` timestamp
- Or: poller does a lightweight SAM.gov health check before processing queued description fetches

## Task 4: UI — Handle 202 Response

- On 202: show info/blue snackbar "Daily API limit reached — queued for automatic fetch tomorrow"
- On 200: existing success behavior (show description)
- On other errors: existing red error snackbar

---

## Broader Applicability

This rate-limit-then-queue pattern could apply to any on-demand SAM.gov call:
- Fetch description (this phase)
- Re-download attachments (Phase 130)
- Any future on-demand API action

Consider making the queue-on-429 logic reusable.

---

## SAM.gov Key 2 Reset Time

Key 2 (1,000/day) resets at **4:00 PM AKT** (midnight UTC). The poller should be aware of this window.
