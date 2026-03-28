# Phase 128: Federal Identifier Extraction from Attachments

## Status: PLANNED

## Context

- We have 25,642 extracted attachment documents with full text
- Our keyword intel extractor (`attachment_intel_extractor.py`) already extracts 16 categories of intelligence (clearance, eval method, vehicle type, recompete signals, incumbent names, etc.)
- But it does NOT extract federal identifiers like PIIDs, UEIs, CAGE codes, contract numbers, solicitation numbers, FAR/DFARS clauses, or wage determination numbers
- Real-world example: solicitation `70LGLY26RGLB00001` (a recompete) has the prior award PIID `70LGLY21CGLB00003` embedded in 11 attachment spreadsheets -- but nothing extracts or cross-references it
- This is the missing link for automatic predecessor contract detection

## Goal

Scan attachment extracted text for federal identifiers, store them in a new cross-reference table, and cross-reference extracted identifiers against known records in our database (fpds_contract, opportunity, entity, etc.) to discover relationships -- especially predecessor contracts for recompetes.

## Extractable Identifier Types

Only identifiers with patterns distinctive enough to extract from free text without excessive false positives:

| Type | Pattern | Length | Regex | Cross-ref Table |
|------|---------|--------|-------|-----------------|
| **PIID** | `{AAC}{FY}{type}{serial}` | 12-17 | `[A-HJ-NP-Z0-9]{5,6}\d{2}[A-Z][A-HJ-NP-Z0-9]{3,8}` | `fpds_contract.contract_id` |
| **UEI** | 12 alphanumeric, no I/O, first char non-zero | 12 | `[A-HJ-NP-Z1-9][A-HJ-NP-Z0-9]{11}` | `entity.uei_sam`, `fpds_contract.vendor_uei` |
| **CAGE Code** | 5 chars, positions 1&5 numeric, 2-4 alphanumeric | 5 | `\d[A-HJ-NP-Z0-9]{3}\d` | `entity.cage_code` |
| **DUNS** (legacy) | 9 digits (context-dependent) | 9 | `\d{9}` near "DUNS" keyword | legacy records |
| **FAR Clause** | `52.2XX-YY` | 9-10 | `52\.2\d{2}-\d{1,3}` | (reference value) |
| **DFARS Clause** | `252.2XX-7YYY` | 12-13 | `252\.2\d{2}-7\d{3}` | (reference value) |
| **Wage Determination** | `YYYY-NNNN` | 9+ | `20\d{2}-\d{4,6}` near wage/SCA/DBA keywords | (reference value) |
| **GSA Schedule** (legacy) | `GS-XXF-XXXXXZ` | 12-14 | `GS-\d{2}F-\d{4,5}[A-Z]?` | `fpds_contract.idv_piid` |
| **USASpending Award ID** | `CONT_AWD_...` composite | variable | `CONT_(?:AWD|IDV)_[A-Z0-9_\-]+` | `usaspending_award.generated_unique_award_id` |
| **Solicitation Number** | Same as PIID structure with R/Q/B at pos 9 | 12-17 | (same PIID regex, type=R/Q/B) | `opportunity.solicitation_number` |

NOT extracting (too short/ambiguous): NAICS (6 digits -- too many false positives), PSC (4 chars), agency codes (3-4 digits), state codes (2 chars), business type codes (2 chars).

## Storage Design

New table: `document_identifier_ref`

```sql
CREATE TABLE document_identifier_ref (
    ref_id              INT AUTO_INCREMENT PRIMARY KEY,
    document_id         INT NOT NULL,                    -- FK to attachment_document
    identifier_type     VARCHAR(30) NOT NULL,            -- 'PIID', 'UEI', 'CAGE', 'DUNS', 'FAR_CLAUSE', 'DFARS_CLAUSE', 'WAGE_DET', 'GSA_SCHEDULE', 'SOLICITATION'
    identifier_value    VARCHAR(200) NOT NULL,           -- the extracted value (normalized: uppercase, no dashes)
    raw_text            VARCHAR(500),                    -- the exact text as found in the document
    context             TEXT,                            -- ±150 chars surrounding context
    char_offset_start   INT,                             -- position in source text
    char_offset_end     INT,
    confidence          ENUM('high','medium','low') DEFAULT 'medium',
    matched_table       VARCHAR(50),                     -- table where cross-ref match found (NULL if no match)
    matched_column      VARCHAR(50),                     -- column matched
    matched_id          VARCHAR(200),                    -- the PK value of matched record
    last_load_id        INT,
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_docid_ref (document_id, identifier_type),
    INDEX idx_identifier (identifier_type, identifier_value),
    INDEX idx_matched (matched_table, matched_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

Also a rollup view per opportunity:

```sql
CREATE OR REPLACE VIEW v_opportunity_identifier_refs AS
SELECT
    oa.notice_id,
    dir.identifier_type,
    dir.identifier_value,
    dir.confidence,
    dir.matched_table,
    dir.matched_id,
    COUNT(*) as mention_count
FROM document_identifier_ref dir
JOIN attachment_document ad ON ad.document_id = dir.document_id
JOIN opportunity_attachment oa ON oa.attachment_id = ad.attachment_id
GROUP BY oa.notice_id, dir.identifier_type, dir.identifier_value,
         dir.confidence, dir.matched_table, dir.matched_id;
```

## Tasks

### Task 1: DDL -- `document_identifier_ref` table
- Add table to `fed_prospector/db/schema/tables/36_attachment.sql`
- Add view `v_opportunity_identifier_refs` to a new or existing view file
- Apply DDL to live database

### Task 2: Identifier pattern definitions
- Add new `_IDENTIFIER_PATTERNS` dict to `attachment_intel_extractor.py` (or a new module `attachment_identifier_extractor.py` if cleaner)
- Each pattern: regex, identifier_type, normalization function (strip dashes, uppercase), confidence rules
- Context-dependent patterns (DUNS, wage determination) require nearby keyword anchors to avoid false positives
- PIID patterns need word boundary matching and length validation

### Task 3: Extraction engine
- Scan each attachment_document's extracted_text for all identifier patterns
- Normalize extracted values (strip dashes, uppercase)
- Deduplicate within a document (same identifier mentioned 50 times = 1 row with mention_count or just 1 row)
- Store in `document_identifier_ref` with char offsets and context

### Task 4: Cross-reference matching
- After extraction, attempt to match each identifier against known records:
  - PIID -> `fpds_contract.contract_id` (also check with/without dashes)
  - UEI -> `entity.uei_sam` and `fpds_contract.vendor_uei`
  - CAGE -> `entity.cage_code`
  - Solicitation -> `opportunity.solicitation_number` and `fpds_contract.solicitation_number`
  - GSA Schedule -> `fpds_contract.idv_piid`
- Populate `matched_table`, `matched_column`, `matched_id` on matched rows
- This is the key deliverable: discovering that attachment text references contract X which exists in our `fpds_contract` table

### Task 5: CLI commands
- `python main.py analyze extract-identifiers [--notice-id X] [--force] [--limit N]`
  - Runs extraction on all documents (or specific opportunity)
  - `--force` re-extracts even if already done
- `python main.py search identifiers --type PIID --value 70LGLY21CGLB00003`
  - Find which documents/opportunities reference a given identifier
- `python main.py analyze cross-ref-identifiers [--notice-id X]`
  - Runs cross-reference matching against known DB records

### Task 6: Integration with daily load
- After `analyze extract-intel` runs, also run identifier extraction on new/updated documents
- Cross-reference step runs after extraction

### Task 7: Predecessor contract detection view
- New view `v_predecessor_candidates` that:
  - For each opportunity, finds PIID-type identifiers extracted from its attachments
  - Joins to fpds_contract to find the actual prior contract
  - Returns: notice_id, predecessor_contract_id, predecessor_vendor_name, predecessor_vendor_uei, predecessor_award_amount, predecessor_set_aside_type, confidence
  - This is the payoff: automatic "this recompete references that prior contract"

### Task 8: Update reference doc
- Add "Regex Patterns for Text Extraction" section to `thesolution/reference/10-FEDERAL-IDENTIFIERS.md`
- Document which identifiers are extractable vs too ambiguous
- Include the regex patterns used

## Dependencies

- Phase 110 (Attachment Intelligence) -- COMPLETE
- Phase 110ZZ (Keyword Intel Enhancements) -- COMPLETE
- Phase 112 (Description Backfill) -- COMPLETE

## Not In Scope

- UI display of extracted identifiers (future phase)
- Extracting identifiers from description_text (Phase 121 covers description intel)
- Extracting identifiers from opportunity structured fields (already captured by loaders)
- Short/ambiguous identifiers (NAICS, PSC, agency codes, state codes)

## Success Criteria

1. For the known test case (`70LGLY26RGLB00001` -> `70LGLY21CGLB00003`), the system automatically discovers the prior PIID in attachments and cross-references it to the fpds_contract record
2. Extraction runs on all 25,642 documents with extracted text
3. Cross-references matched against fpds_contract, entity, and opportunity tables
4. CLI commands allow querying "which opportunities reference this contract?"
5. `v_predecessor_candidates` view provides direct predecessor lookup for recompetes
