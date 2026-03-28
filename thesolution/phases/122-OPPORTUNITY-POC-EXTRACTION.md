# Phase 122: Opportunity Point of Contact Extraction

**Status:** PLANNED
**Priority:** High — contact data exists in raw JSON but is never extracted to the opportunity table
**Dependencies:** None

---

## Summary

The SAM.gov Opportunity API returns `pointOfContact` data (name, email, phone, fax, title) for each opportunity. This data is stored in `stg_opportunity_raw.raw_json` but the `opportunity_loader` never extracts it to the `opportunity` table or related tables. The `contracting_officer` and `opportunity_poc` tables exist in the schema (designed in Phase 9) but may not be populated.

## Discovery

Sample raw JSON from `stg_opportunity_raw`:
```json
{
  "pointOfContact": [
    {
      "type": "primary",
      "fullName": "RACHEL M. OPPERMAN, N722.23, PHONE (215)697-2560",
      "email": "RACHEL.M.OPPERMAN.CIV@US.NAVY.MIL",
      "phone": null,
      "fax": null,
      "title": null
    }
  ]
}
```

Note: phone numbers are sometimes embedded in `fullName` rather than in the `phone` field.

---

## Research Needed

1. **Update loading process** — Extend `opportunity_loader.py` to extract POC data from the API response into the appropriate tables (`contracting_officer`, `opportunity_poc`, or new columns on `opportunity`). Determine which approach fits best.

2. **Backfill existing data** — All historical POC data exists in `stg_opportunity_raw.raw_json`. Build a backfill to extract it without re-calling the API.

3. **API and UI** — Ensure POC data flows through the C# API and displays on the opportunity detail page in the UI.

4. **Contact deduplication** — Check existing deferred phases for contact normalization plans:
   - 500E: Entity POC Normalization (deferred from Phase 44.10) — `entity_poc` table has 750K+ denormalized rows
   - 500H: Database Denormalization Audit — identifies `opportunity_poc` as having the same duplication pattern
   - Phase 200: Full Database Normalization — includes contact normalization strategy
   - 120/O4: POC Officer Lookup Race Condition bug in `opportunity_loader.py:561-577`

   Determine whether this phase should just populate the existing tables or coordinate with the normalization effort.
