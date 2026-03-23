# Phase 110F: Request Poller Service

**Status:** PLANNED
**Priority:** Medium — needed for UI buttons to actually trigger background work
**Dependencies:** Phase 43 (demand loader exists), Phase 110C (adds ATTACHMENT_ANALYSIS request type)

---

## Summary

The `data_load_request` table is a generic job queue used by the UI to trigger background work (award loading, AI analysis). The Python poller (`python main.py demand process-requests --watch`) processes these requests, but currently must be run manually — it's not part of `fed_prospector.py start/stop`.

Add the poller as a managed service so it runs automatically when the system is started.

---

## Scope

- Add `poller` as a fourth service in `fed_prospector.py` (alongside db, api, ui)
- `start all` → starts db, api, ui, **poller**
- `stop all` → stops poller, ui, api, db
- `start poller` / `stop poller` — manage independently
- Runs in a minimized console window like the other services

## What depends on this

- **Phase 43** — Award on-demand loading (USASPENDING_AWARD, FPDS_AWARD)
- **Phase 110C** — AI attachment analysis triggered from UI (ATTACHMENT_ANALYSIS)
- Any future request types added to `data_load_request`

## Files to modify

| File | Change |
|------|--------|
| `fed_prospector.py` | Add `poller` to SERVICE_MAP with start/stop/check functions |

## Notes

- Without this, users must manually run `python main.py demand process-requests --watch` in a separate terminal
- The poller should start after db and api (it needs both), but before or alongside ui
- Consider health check: verify the poller is responsive, not hung on a long request
