# Phase 93 — Federal Hierarchy Level 3 Offices

**Status**: BACKLOG
**Priority**: MEDIUM
**Depends on**: None (Phase 90 recommended first for `get_resumable_load()` helper, but can be built standalone)

---

## Context

The federal hierarchy loader (`load hierarchy`) currently loads only Level 1 (Department/Ind. Agency, ~170 records) and Level 2 (Sub-Tier, ~738 records) from the SAM.gov Federal Hierarchy **Vendor API**. Level 3 (Office) organizations are NOT returned by the Vendor API's `/v1/orgs` search endpoint because `fhorgtype` only supports "Department/Ind-agency" and "Sub-tier" — there is no "Office" option.

To get Level 3 offices, we need a **different Vendor API endpoint**: `/v1/org/hierarchy?fhorgid={id}`, which returns the children of a given org. By calling this for each Level 2 sub-tier, we can fetch all their Level 3 office children.

This requires ~738 Vendor API calls (one per sub-tier). With key 2 at 1,000/day, this may take 1-2 days of budget, so **resumability is critical**.

> **Terminology reminder**: "Vendor API" = external SAM.gov endpoints, rate-limited, called only by Python `load` commands. "App API" = our C# ASP.NET Core backend. This phase is entirely Vendor API work.

---

## The Two Vendor API Endpoints

| Vendor API Endpoint | Current Use | Level 3 Support |
|---------------------|-------------|-----------------|
| `/prod/federalorganizations/v1/orgs` | Used by `load-hierarchy` today | No — `fhorgtype` has no "Office" value |
| `/prod/federalorganizations/v1/org/hierarchy` | NOT wired up | Yes — returns children of any org by `fhorgid` |

### Vendor API OpenAPI Specs
- `/v1/orgs`: `thesolution/sam_gov_api/fh-public-org.yml`
- `/v1/org/hierarchy`: `thesolution/sam_gov_api/fh-public-hierarchy.yml`

---

## Existing Patterns to Reuse

| Pattern | Source File | Description |
|---------|------------|-------------|
| Resume via completed list tracking | `cli/awards.py` | `completed_combos` list in parameters JSON |
| Page-by-page checkpoint | `etl/load_manager.py` | `save_load_progress()` per page |
| Budget exhaustion with progress save | `cli/awards.py` | `--max-calls` preserves state for next run |
| Batch upsert with change detection | `etl/fedhier_loader.py` | `load_organization_batch()` with SHA-256 hashing |
| Org normalization | `etl/fedhier_loader.py` | `_normalize_org()` already computes level from fhorgtype |
| Vendor API client base | `api_clients/sam_fedhier_client.py` | Inherits `BaseAPIClient`, has rate limiting + retries |

---

## Items to Address

### HIGH PRIORITY

**P93-1 — Add Vendor API hierarchy endpoint method to SAMFedHierClient**
File: `fed_prospector/api_clients/sam_fedhier_client.py`

- Add `HIERARCHY_ENDPOINT = "/prod/federalorganizations/v1/org/hierarchy"` (Vendor API endpoint)
- Add `get_org_children(fhorgid, limit=100, offset=0)` method that calls the Vendor API hierarchy endpoint with the given `fhorgid`
- Add `iter_org_children_pages(fhorgid, ...)` page iterator for automatic pagination (follows the pattern of existing `iter_pages()` in base client)
- The Vendor API hierarchy endpoint supports `limit` and `offset` query parameters for pagination

---

**P93-2 — Add `load-offices` CLI command**
File: `fed_prospector/cli/fedhier.py`

- New subcommand `load-offices` (separate from existing `load-hierarchy` to keep concerns clean)
- Query all Level 2 sub-tiers from `federal_organization` table: `SELECT fh_org_id, name FROM federal_organization WHERE level = 2`
- For each sub-tier, call `get_org_children()` / `iter_org_children_pages()` to fetch its Level 3 office children from the Vendor API
- Use existing `load_organization_batch()` to upsert offices (loader already handles SHA-256 change detection)
- Flags: `--max-calls` (Vendor API budget control), `--force` (restart from scratch), `--key` (Vendor API key selection)
- Separate `source_system = "SAM_FEDHIER_OFFICES"` from Level 1-2 loads (`"SAM_FEDHIER"`) to avoid resume conflicts

---

**P93-3 — Resume/restart support**
File: `fed_prospector/cli/fedhier.py`

- Use `load_manager.get_resumable_load("SAM_FEDHIER_OFFICES")` to find incomplete loads
  - If Phase 90 is not yet done, implement equivalent inline: query `etl_load_log` for `status = 'SUCCESS'` and `JSON_EXTRACT(parameters, '$.complete') = false`
- Store in parameters JSON:
  ```json
  {
    "completed_orgs": ["fhorgid_1", "fhorgid_2", ...],
    "total_subtiers": 738,
    "current_org": "fhorgid_123",
    "current_page": 0,
    "complete": false,
    "calls_made": 247,
    "total_fetched": 12350
  }
  ```
- Save progress after each sub-tier's offices are fully loaded via `save_load_progress()`
- On resume: skip sub-tiers whose `fhorgid` is in `completed_orgs`
- Budget exhaustion (`--max-calls` reached): save state and exit cleanly; re-run next day continues from last completed sub-tier
- `--force` flag: ignore previous progress, start fresh

---

### MEDIUM PRIORITY

**P93-4 — Verify `_normalize_org()` handles Vendor API hierarchy endpoint response format**
File: `fed_prospector/etl/fedhier_loader.py`

- The Vendor API hierarchy endpoint (`/v1/org/hierarchy`) may return data in a different JSON shape than the Vendor API search endpoint (`/v1/orgs`)
- Compare Vendor API response schemas from OpenAPI specs:
  - `/v1/orgs` returns `orgList[].org` with nested fields
  - `/v1/org/hierarchy` returns `orgHierarchy` with `hierarchyDepartment` and child structures
- Adapt `_normalize_org()` if needed, or write a thin adapter in the CLI/client layer to reshape the Vendor API hierarchy response into the format `_normalize_org()` expects
- Ensure `parent_org_id` is correctly set from the queried sub-tier's `fhorgid` (the Vendor API hierarchy endpoint may not include this explicitly in child records)

---

**P93-5 — Testing and verification**
Files: `fed_prospector/tests/`

- Verify office records appear with `level = 3`, `fh_org_type = 'Office'`
- Verify `parent_org_id` correctly points to the sub-tier
- Verify resume works: run with `--max-calls 5`, then re-run and confirm it continues from the last completed sub-tier
- Verify `--force` restarts from scratch
- Verify budget exhaustion preserves state for next run

---

## Vendor API Gotchas to Handle

1. **Different Vendor API response shape** — `/v1/org/hierarchy` returns a hierarchical structure, not a flat list like `/v1/orgs`. Need to extract child org records from the Vendor API hierarchy response.
2. **Vendor API pagination** — The hierarchy endpoint supports `limit` and `offset`, but some sub-tiers may have very few (or zero) offices. Handle empty results gracefully.
3. **Shared 1,000/day Vendor API rate limit** — All SAM.gov Vendor API calls share the same daily budget. If running after other loaders, budget may already be partially consumed.
4. **~738 sub-tiers = 738+ Vendor API calls minimum** — Even with no pagination needed, this exceeds half the daily budget. Plan for 1-2 day completion window.
5. **Parent org ID** — The Vendor API hierarchy endpoint may not explicitly include the parent `fhorgid` in each child record. May need to inject it from the queried sub-tier.
6. **Some sub-tiers may have no offices** — These should be marked as completed (added to `completed_orgs`) to avoid retrying on resume.

---

## Risks and Mitigation

| Risk | Mitigation |
|------|-----------|
| ~738 Vendor API calls exceeds single-day budget | Resume system handles multi-day loading; `--max-calls` controls spend per run |
| Vendor API hierarchy endpoint response shape differs from search endpoint | P93-4 explicitly verifies and adapts `_normalize_org()` |
| Sub-tiers with zero offices waste Vendor API calls | Inevitable but cheap (1 call each); mark as completed to avoid retries |
| Vendor API rate limit errors mid-run | BaseAPIClient already handles rate limits with backoff; progress saved on exit |
| Stale Level 2 data (sub-tiers added/removed since last load) | Re-query `federal_organization` table each run; new sub-tiers automatically included |
| Multiple simultaneous office loads could conflict | Single-instance limitation (same as other loaders); document in CLI help |
| Phase 90 `get_resumable_load()` not yet available | Can implement equivalent resume logic inline; refactor later when Phase 90 lands |

---

## Files Modified

| File | Change |
|------|--------|
| `fed_prospector/api_clients/sam_fedhier_client.py` | Add Vendor API `HIERARCHY_ENDPOINT`, `get_org_children()`, `iter_org_children_pages()` |
| `fed_prospector/cli/fedhier.py` | Add `load-offices` command with resume, `--max-calls`, `--force`, `--key` |
| `fed_prospector/etl/fedhier_loader.py` | Verify/adapt `_normalize_org()` for Vendor API hierarchy response format |
| `thesolution/sam_gov_api/fh-public-hierarchy.yml` | Reference only — Vendor API OpenAPI spec for hierarchy endpoint |

---

## Verification Checklist

- [ ] `python main.py load offices --dry-run` shows total sub-tiers, resume state, estimated API calls
- [ ] `python main.py load offices --max-calls 5` partial run saves progress with `completed_orgs` in `etl_load_log`
- [ ] `python main.py load offices` re-run resumes from saved sub-tier position
- [ ] `python main.py load offices --force` starts fresh ignoring resume state
- [ ] Office records in `federal_organization` have `level = 3` and `fh_org_type = 'Office'`
- [ ] Office records have correct `parent_org_id` pointing to their sub-tier
- [ ] `SELECT COUNT(*) FROM federal_organization WHERE level = 3` returns expected office count
- [ ] Zero-office sub-tiers are added to `completed_orgs` and not retried
- [ ] Budget exhaustion (`--max-calls` reached) preserves state; re-run next day continues
- [ ] `etl_load_log.parameters` JSON contains correct `complete`, `completed_orgs`, `calls_made` fields
