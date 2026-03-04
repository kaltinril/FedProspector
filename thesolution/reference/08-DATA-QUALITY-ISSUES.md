# Known Data Quality Issues

Discovered during SAM.gov imports. Handled by ETL data cleaners in `fed_prospector/etl/`.

---

## Entity Extract (DAT file) Issues

1. **ZIP codes containing city/state/country names** -- 9,294 records in first import
2. **ZIP codes containing PO BOX data** -- 27 records
3. **State fields containing dates** -- e.g., "05/03/1963"
4. **Foreign addresses with province names > 2 chars** in state field
5. **Non-ASCII characters in country names** -- Reunion, Cote d'Ivoire
6. **Missing 3-letter country codes** -- XKS (Kosovo), XWB (West Bank), XGZ (Gaza)
7. **CAGE codes with multiple values** -- separated by comma+space
8. **NAICS codes from retired vintages** -- not in current lookup tables
9. **Escaped pipe characters in DAT files** -- `|\|` must become `||`
10. **Dates in YYYYMMDD format** -- need conversion to DATE type
11. **SBA type entries concatenate code+date** -- e.g., "A620291223" = code "A6" + date "20291223"
12. **Duplicate NAICS entries** -- same code, different flags (7 occurrences in monthly extract)

## Opportunity API Issues

13. **`fullParentPathName` is dot-separated** -- not separate department/subTier/office fields
14. **`description` field is a URL, not text** -- full text requires separate authenticated fetch
15. **Rejects date ranges of exactly 365 days** -- error: "Date range must be null year(s) apart"; use 364-day max chunks
16. **Rejects Feb 29 as start date** -- historical load skips leap day
17. **`pop_state` can contain ISO 3166-2 codes > 2 chars** -- e.g., IN-MH for India-Maharashtra; column widened to VARCHAR(6)

## Subaward API Issues

19. **Dict vs scalar fields** -- `recoveryModelQ1`, `recoveryModelQ2`, `primeNaics`, `subAwardDescription` return as `{code, description}` dicts from live API but as plain strings in test fixtures. Loader uses `isinstance(dict)` guards.
20. **Loader was reading wrong address field** -- `placeOfPerformance` is the correct POP field, not `entityPhysicalAddress` (entity mailing address). Loader bug fixed 2026-03-03. Prod subaward POP data needs reload.
21. **Foreign POP `state.code` is null** -- for non-US addresses, `state.code` returns `null`; `state.name` has the full province/state name. Column widened to VARCHAR(100).

## Awards API Issues

18. **Dates in MM/DD/YYYY format** -- not ISO 8601; awards_loader converts during load
