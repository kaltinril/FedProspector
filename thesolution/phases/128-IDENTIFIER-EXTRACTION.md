# Phase 128: Federal Identifier Extraction from Attachments

## Status: IN PROGRESS

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

## Implementation Summary

### Task 1: DDL -- DONE
- Added `document_identifier_ref` table to `fed_prospector/db/schema/tables/36_attachment.sql`
- Added views `v_opportunity_identifier_refs` and `v_predecessor_candidates` to `fed_prospector/db/schema/views/80_identifier_refs.sql`
- **User must apply DDL to live database** (table create + view creates)

### Task 2-3: Identifier Extraction Engine -- DONE
- New module: `fed_prospector/etl/attachment_identifier_extractor.py`
- `AttachmentIdentifierExtractor.extract_identifiers()` scans all documents
- Deduplicates within each document (same type+value = 1 row)
- Stores char offsets and surrounding context

### Task 4: Cross-reference Matching -- DONE
- `AttachmentIdentifierExtractor.cross_reference()` matches against:
  - PIID/SOLICITATION -> `fpds_contract.contract_id`, `fpds_contract.solicitation_number`, `opportunity.solicitation_number`
  - UEI -> `entity.uei_sam`, `fpds_contract.vendor_uei`
  - CAGE -> `entity.cage_code`
  - GSA_SCHEDULE -> `fpds_contract.idv_piid`
- Populates `matched_table`, `matched_column`, `matched_id`

### Task 5: CLI Commands -- DONE
- `python main.py extract identifiers [--notice-id X] [--force] [--batch-size N]`
- `python main.py extract cross-ref-identifiers [--notice-id X] [--batch-size N]`
- `python main.py search identifiers --type PIID --value 70LGLY21CGLB00003`

### Task 6: C# API Endpoint -- DONE
- EF Core model: `DocumentIdentifierRef.cs`
- DTOs: `IdentifierRefDto`, `PredecessorCandidateDto`, `OpportunityIdentifiersDto`
- Service: `IAttachmentIntelService.GetIdentifierRefsAsync(noticeId)`
- Endpoint: `GET /api/opportunities/{noticeId}/identifier-refs`

### Task 7: UI Types -- DONE
- TypeScript interfaces added to `ui/src/types/api.ts`

### Task 8: Predecessor Contract View -- DONE
- `v_predecessor_candidates` view joins identifier refs to fpds_contract
- Returns predecessor PIID, vendor name, UEI, award amount, set-aside type

## Remaining Work

- Apply DDL to live database (user action)
- Run extraction on all documents
- Run cross-reference matching
- Integration with daily load (future)

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
