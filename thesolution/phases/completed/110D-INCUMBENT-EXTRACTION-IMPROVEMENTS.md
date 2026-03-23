# Phase 110D: Incumbent Name Extraction Improvements

**Status:** COMPLETE
**Priority:** Low — quality improvement to existing keyword extraction pipeline
**Dependencies:** Phase 110 (keyword intel extraction — complete)
**Out-of-order:** Yes — can be done independently of 110C
**Completed:** All 6 tasks implemented in `attachment_intel_extractor.py`. Code comments reference "Phase 110D" throughout.

---

## Problem

The incumbent name extractor (`attachment_intel_extractor.py`, `_extract_incumbent_name()` at line 673) had several weaknesses discovered during data review:

### 1. False Positives from Linking Phrases

The regex requires an explicit linking phrase ("incumbent is X", "current contractor: X") but still produces false positives when the text following the link isn't actually a company name. The false positive list (`_INCUMBENT_FALSE_POSITIVES`) only checks single words and the first word, not multi-word phrases.

**Confirmed false positives from production data:**

- **"Question"** (notice `41a0122ced9b4912b1dc8a2060420204`): Q&A spreadsheet had `incumbent: Question(1) Will the Government...` — the colon pattern (line 91) matched "Question" as a name. Source: `USSOCOM J6 COMSATCOM RFI Q-A (2).xlsx` attachment_id 5224, offset 21466.
- **"must detail"** (notice `c72fb61d54324e33988e22fdc6a3bacd`): Extracted from description_text (attachment_id NULL, intel_id 2), not from the PDF attachment. The PDF had "current incumbent must detail how the offeror proposes..." but the actual extraction happened in an earlier run against the same text stored as a virtual attachment.

### 2. No Frequency-Based Tiebreaking

When multiple incumbent names are extracted from a single document (or across attachments for the same opportunity), the consolidation at line 739 used last-high-confidence-wins with no consideration of how many times each name appears. A name mentioned 10 times should beat a name mentioned once.

### 3. Cross-Attachment Conflicts Are Silent

Each attachment was processed independently. The backfill to `opportunity.incumbent_name` (`_update_opportunity_columns()` at line 1195) ran after **each** attachment and did a blind `UPDATE SET` — last one processed wins. There was no post-processing step that compared results across all attachments for an opportunity.

### 4. No Document-Type Awareness

A SOW or performance work statement should carry more weight than a Q&A spreadsheet or pricing template. Currently all document types are treated equally — a false positive from a Q&A spreadsheet can overwrite a correct extraction from the SOW.

### 5. Stale Intel Rows

Intel rows with `attachment_id=NULL` from earlier extraction runs can persist and influence the backfill even when later runs extract correctly. See notice `c72fb61d54324e33988e22fdc6a3bacd` where intel_id 2 (stale, from 11:25am) had "must detail" but intel_id 4 (re-run at 13:52) correctly had NULL.

---

## Deliverables

### Task 1: Occurrence-Based Confidence -- DONE

Implemented in `_consolidate_matches()` at lines 785-804. Tracks frequency via `Counter`, picks best name by `(count, max_confidence)`. Stores count in `intel["incumbent_name_count"]`.

In `_consolidate_matches()`, track frequency of each extracted incumbent name. Use occurrence count as a tiebreaker:

- Count how many times each distinct name is extracted within a document
- When multiple names are found, prefer the most frequently mentioned
- If counts are equal, prefer the one with higher base confidence
- Store the count in the intel row (new column or in `recompete_details`) for transparency

### Task 2: Improved False Positive Filtering -- DONE

Implemented in `_extract_incumbent_name()` at lines 705-724. All four filter layers active: expanded `_INCUMBENT_FALSE_POSITIVES` (line 124), Q&A `(number)` rejection (line 711), all-words common-English check (line 718), single-word skepticism, and gov-org indicator check.

Multiple layers of defense:

1. **Expand `_INCUMBENT_FALSE_POSITIVES`** — add gov-doc words that appear after linking phrases:
   - `"question"`, `"response"`, `"tasked"`, `"performing"`, `"providing"`, `"currently"`
   - `"unknown"`, `"tbd"`, `"n/a"`, `"na"`, `"none"`, `"section"`, `"paragraph"`, `"reference"`, `"see"`, `"per"`

2. **All-words check** — reject if EVERY word in the extracted name is a common English word (not just first word). Kills "must detail", "shall provide", etc.:
   ```python
   if all(w.lower() in _COMMON_ENGLISH_WORDS for w in words):
       continue
   ```

3. **Reject names followed by `(number)`** — dead giveaway of Q&A format, not a company name:
   ```python
   post_context = text[name_end:name_end + 5]
   if re.match(r'\s*\(\d', post_context):
       continue
   ```

4. **Single-word name skepticism** — require single-word names to either have a corporate suffix, be all-caps (acronym like "SAIC"), or match a known entity in our awards data.

### Task 3: Cross-Attachment Incumbent Resolution -- DONE

Implemented as `_resolve_incumbent_for_opportunity()` at line 1016. Uses `_FILENAME_WEIGHTS` (line 1009) for document-type weighting (SOW=3, J&A/RFP=2, Q&A=1). Resolves across all intel rows for a notice, with occurrence count + doc-type weight tiebreaking.

Move the backfill from per-attachment to post-processing:

- Do NOT update `opportunity.incumbent_name` inside `_update_opportunity_columns()` during per-attachment processing
- After all attachments for a notice_id are processed, query all intel rows that have an incumbent_name
- If all agree, use that name
- If they disagree, pick the most frequently extracted name across all attachments
- Log a warning when conflicts exist so they can be reviewed
- Consider document-type weighting: SOW/PWS > RFP body > Q&A docs > pricing sheets (can use filename heuristics)

### Task 4: Stale Intel Row Cleanup -- DONE

Implemented as `_cleanup_stale_intel_rows()` at line 1167. Called at line 437 when `force=True`. Deletes consolidated rows (`attachment_id IS NULL`) before re-extraction.

- When re-running extraction with `--force`, delete or update stale intel rows (especially `attachment_id=NULL` rows from earlier runs)
- Ensure the backfill only considers current intel rows

### Task 5: Incumbent UEI Resolution via Entity Table Lookup -- DONE

Implemented as `_resolve_incumbent_uei()` at line 1113. Called from `_resolve_incumbent_for_opportunity()` after name is finalized. LIKE query against `entity.legal_business_name`, sets UEI only when exactly 1 match found.

**Finding:** UEIs never appear in solicitation documents. Reviewed all 8 legitimate incumbent extractions — zero contained an actual UEI. The only 12-char alphanumeric match was the English word "ANNOUNCEMENT". Government solicitations (RFPs, J&As, sources sought, Q&As) simply don't include the incumbent's UEI.

**Approach:** Resolve `incumbent_uei` by cross-referencing the extracted `incumbent_name` against the `entity` table (SAM.gov registrations). Data review showed this works for most cases:

| Extracted Name | Entity Match | UEI |
|---|---|---|
| ManTech | MANTECH ADVANCED SYSTEMS INTERNATIONAL, INC. | ERE6S22HCZB6 (+ 4 others) |
| Kangaroo Pick-Up | KANGAROO PICK-UP AND DELIVERY SERVICE, INC. | PJYHFKK41W47 |
| Hendall, Inc | HENDALL INC | P83UA59FQ9V8 |
| Byre Brothers Inc | BYRE BROTHERS INC | FEDLH65XP2V5 |
| Tek Source | TEK SOURCE SOLUTIONS / TEK SOURCE USA | MJHCK6NZW4C7 / LGT6SCL2P2J1 |
| Logistico LLC | LOGISTICO LLC | YM2EZMNJW143 |
| SimbaCom | No match | — |
| Ingrams Cleaners | No match | — |

6/8 resolved (75%). Misses are likely smaller businesses not in our entity data or registered under different names.

**Implementation:**
- After incumbent name is finalized (post Task 3 cross-attachment resolution), do a `LIKE` lookup against `entity.legal_business_name`
- If exactly 1 match, set `opportunity.incumbent_uei` automatically
- If multiple matches (e.g. ManTech has 5 entities), set to NULL and log for manual review or AI resolution
- If no match, leave NULL
- Could also cross-reference against `usaspending_award.recipient_name` for the same opportunity's NAICS/agency to disambiguate

### Task 6: Fix Existing False Positives -- DONE

The improved filters in Tasks 1-2 now reject both known false positives ("Question" and "must detail"). Re-running extraction with `--force` cleans up stale rows (Task 4) and applies the new filters.

After improving the extractor:

- Re-run keyword intel extraction on all opportunities with `--force`
- Clear false positive incumbent names from the opportunity table
- Verify the two known false positives are fixed

---

## Known False Positives to Fix

| notice_id | Extracted Name | Root Cause | Source |
|-----------|---------------|-----------|--------|
| `41a0122ced9b4912b1dc8a2060420204` | "Question" | Colon pattern matched `incumbent: Question(1)` in Q&A spreadsheet | attachment_id 5224, offset 21466 |
| `c72fb61d54324e33988e22fdc6a3bacd` | "must detail" | Stale intel row (intel_id 2, attachment_id NULL) from earlier run; text was "current incumbent must detail how..." | description_text virtual attachment |

---

## Data Analysis Summary (2026-03-22)

Reviewed all 23 intel rows with incumbent names across the production database:

- **8 unique incumbent names** extracted (excluding duplicates across attachments/description_text)
- **2 confirmed false positives**: "Question", "must detail"
- **6 legitimate extractions**: ManTech, Kangaroo Pick-Up, Hendall Inc, Byre Brothers Inc, SimbaCom, Tek Source, Logistico LLC, Ingrams Cleaners
- **0 documents contained UEIs** — confirmed across all extracted documents; UEIs do not appear in federal solicitation documents
- **6/8 (75%) incumbent names resolvable** to UEI via `entity` table lookup
- **All documents referenced "incumbent" generically** — names were only captured when explicit linking phrases existed (e.g. "current contractor is X", "incumbent: X")

---

## Implementation Notes

- Primary file: `fed_prospector/etl/attachment_intel_extractor.py`
- Key functions: `_extract_incumbent_name()` (line 673), `_consolidate_matches()` (line 739), `_update_opportunity_columns()` (line 1195), `_resolve_incumbent_for_opportunity()` (line 1016), `_resolve_incumbent_uei()` (line 1113), `_cleanup_stale_intel_rows()` (line 1167)
- Entity lookup for UEI resolution: `entity.legal_business_name` → `entity.uei_sam`
- Occurrence count stored in `intel["incumbent_name_count"]` and written to `confidence_details`
- Re-extraction with `--force` flag supported by the CLI; also triggers stale row cleanup
- This is independent of the AI tier (110C Task 2) — these improvements benefit the regex layer regardless
- Document-type weighting implemented via `_FILENAME_WEIGHTS` (line 1009) using filename heuristics (SOW/PWS=3, J&A/RFP=2, Q&A=1)
