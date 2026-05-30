# 13 — NAICS Codes & SBA Size Standards

Reference for developers and product folks building NAICS-aware features in FedProspect.
It explains the domain (what NAICS codes and SBA size standards *are*) and ties each concept
to the specific tables and columns in this database, so feature work uses real schema and real rules.

> **Scope note:** This is a domain primer, not legal advice. Size-eligibility computed by
> FedProspect is *indicative*. The actual SBA small-business determination includes affiliate
> revenues and other rules we do not model (see [§5](#5-how-fedprospect-uses-this)).

---

## 1. NAICS structure

**NAICS** = North American Industry Classification System. It is the standard the U.S. federal
government uses to classify business establishments by what they do. Every federal contract
opportunity and award is tagged with a NAICS code, and small-business size eligibility is defined
*per NAICS code*. NAICS is therefore the backbone of nearly every prospecting and pricing feature.

### The 5 levels

A NAICS code is hierarchical. The number of digits tells you how specific it is. Each additional
digit narrows the classification one level deeper:

| Digits | Level (`code_level`) | Level name (`level_name`) | Meaning |
|-------:|:--------------------:|:--------------------------|:--------|
| 2 | 1 | `Sector` | Broadest grouping (e.g. all of manufacturing) |
| 3 | 2 | `Subsector` | A slice of a sector |
| 4 | 3 | `Industry Group` | A group of related industries |
| 5 | 4 | `NAICS Industry` | A specific industry (comparable across NAFTA countries) |
| 6 | 5 | `National Industry` | The most specific — U.S.-specific detail |

The leading digits of a code are always the code of its parent. So `541512` lives *inside*
`54151`, which lives inside `5415`, inside `541`, inside `54`.

### Worked example: walking `541512` down all 5 levels

| Code | Digits | Level | Title |
|:-----|-------:|:------|:------|
| `54` | 2 | Sector | Professional, Scientific, and Technical Services |
| `541` | 3 | Subsector | Professional, Scientific, and Technical Services |
| `5415` | 4 | Industry Group | Computer Systems Design and Related Services |
| `54151` | 5 | NAICS Industry | Computer Systems Design and Related Services |
| `541512` | 6 | National Industry | Computer Systems Design Services |

Read top-to-bottom, each row is the parent of the one below it. `541512` ("Computer Systems
Design Services") is a national industry inside the broad "Professional, Scientific, and Technical
Services" sector.

### How the hierarchy lives in this DB

The hierarchy is stored in **`ref_naics_code`**, with the parent-child relationship made explicit
by a self-referential column rather than only being implied by digit prefixes:

| Column | Notes |
|:-------|:------|
| `naics_code` (PK) | `VARCHAR(11)` — the code. Most are 2–6 digit numeric; a few carry letter suffixes for SBA exception sub-categories (e.g. `115310e1`). |
| `description` | Industry title. |
| `code_level` | `TINYINT` 1–5 (computed at load — see table above). |
| `level_name` | The friendly level name (`Sector` … `National Industry`). |
| `parent_code` | The code one level up (its prefix minus the last digit; `NULL` for 2-digit sectors). |
| `year_version` | NAICS revision year. Currently `2022` (primary) plus `2017` codes loaded with `INSERT IGNORE` for overlaps. |
| `is_active` | `CHAR(1)` `Y`/`N`. |
| `footnote_id` | Optional link to `ref_naics_footnote` (see [§4](#4-footnotes--exceptions)). |

`code_level`, `level_name`, and `parent_code` are derived at load time by
`fed_prospector/etl/reference_loader.py` (`_naics_hierarchy()`), driven by the digit count of the
code. This means you can do real recursive / hierarchy queries (e.g. "all national industries
under sector 54") via `parent_code` joins, without parsing digit prefixes in application code.

---

## 2. 5-year revisions & concordance (brief)

NAICS is revised on a **5-year cycle**: 2012 → 2017 → 2022 → 2027. Each revision can rename, merge,
or split codes to reflect how industries evolve. **The data currently loaded is the 2022 revision**
(with 2017 codes also present for backfilling older awards).

Examples of real cross-revision changes (2017 → 2022):

| Change type | Example |
|:------------|:--------|
| **MERGE** | `452111` (department stores) + `452112` (discount department stores) → `455110` (Department Stores) |
| **RENAME** | `453220` (Gift, Novelty, and Souvenir Stores) → `459420` (same activity, new code) |
| **SPLIT** | `454110` (Electronic Shopping and Mail-Order Houses) split into more specific successor codes |

Because of this churn, comparing data across revisions correctly requires a **concordance / crosswalk**
(an old-code ↔ new-code mapping the Census Bureau publishes alongside each revision).

> **Out of scope for now (intentional):** FedProspect does **not** maintain a cross-revision
> concordance table. This is deferred until SBA publishes the 2027 size-standard file, at which
> point a single crosswalk effort can cover both the NAICS revision and the corresponding size
> standards. Until then, treat loaded codes as 2022 (with 2017 fallback) and do not assume
> automatic mapping between revisions. This note exists so future readers know the absence of a
> concordance table is a deliberate decision, not an oversight.

---

## 3. SBA size standards

A **size standard** is the ceiling below which a firm counts as a **small business** for a given
NAICS code. It is the central rule behind small-business set-asides: only firms *at or below* the
size standard for an opportunity's NAICS may bid that opportunity as a small business (and qualify
for WOSB / 8(a) / etc. set-asides layered on top).

Size standards are defined **per NAICS code** and come in **two measure types**:

| `size_type` | Measure | Units | "Small" means |
|:-----------:|:--------|:------|:--------------|
| `M` | Average annual **receipts** (revenue) | **\$ millions** | average annual receipts **≤** the threshold |
| `E` | Number of **employees** | head count | employee count **≤** the threshold |

A firm is **small (eligible)** for a NAICS when its relevant measure is **at or below** the
threshold. Example: if NAICS `541512` has a `size_type = 'M'` standard of `34.00`, a firm is small
for that NAICS when its average annual receipts are **≤ \$34 million**. If a manufacturing NAICS has
`size_type = 'E'` of `1000`, a firm is small when it has **≤ 1,000 employees**.

### Where this lives in the DB

Stored in **`ref_sba_size_standard`**:

| Column | Notes |
|:-------|:------|
| `id` (PK) | Auto-increment. |
| `naics_code` | FK to `ref_naics_code(naics_code)`. |
| `industry_description` | Industry title as published by SBA. |
| `size_standard` | `DECIMAL(13,2)` — the threshold value. For `M` it is in **\$ millions**; for `E` it is a **head count**. |
| `size_type` | `CHAR(1)` — `M` (receipts) or `E` (employees). |
| `footnote_id` | Optional link to a footnote (see [§4](#4-footnotes--exceptions)). |
| `effective_date` | When the standard took effect. |

> **Unit gotcha:** `size_standard` for type `M` is *millions of dollars*, not raw dollars. A value
> of `34.00` means \$34,000,000. Org revenue (`organization.annual_revenue`) is stored in **raw
> dollars** (`DECIMAL(18,2)`), so any eligibility comparison must convert — e.g. compare
> `annual_revenue` against `size_standard * 1_000_000`.

### Data source & loading

- **File:** `workdir/converted/local database/data_to_import/naics_size_standards.csv`
- **Header:** `NAICS Codes,NAICS Industry Description,Size_standard,TYPE,Footnote`
- **Loader:** `fed_prospector/etl/reference_loader.py` (`load_size_standards()`), which truncates
  and reloads the table, validates each `naics_code` against `ref_naics_code` (skipping codes not
  present), and maps the CSV's `TYPE` column into `size_type`.

---

## 4. Footnotes & exceptions

Some size standards aren't a single flat number — they carry a **footnote** describing a special
rule or exception for a sub-category of the industry. Example patterns: a NAICS may have a higher
ceiling for a specific kind of work, an exception sub-code, or a different basis of measurement
under defined conditions.

Footnotes live in **`ref_naics_footnote`**:

| Column | Notes |
|:-------|:------|
| `footnote_id` | Part of composite PK. Referenced from `ref_naics_code.footnote_id` and `ref_sba_size_standard.footnote_id`. |
| `section` | Part of composite PK — which section/area the footnote applies to. |
| `description` | `TEXT` — the human-readable rule. |

- **Data source:** `workdir/converted/local database/data_to_import/footnotes.csv`
- **Header:** `ID,section,Description`

**Why this matters for features:** a NAICS row may reference a footnote that *changes its size
standard for certain work*. So "what's the size standard for NAICS X?" is not always a single
number — if a footnote is attached, the effective threshold can depend on the specific scope of
work. Eligibility UIs and pWin logic should surface the footnote text (or at least flag its
presence) rather than silently treating the headline number as absolute. The letter-suffixed NAICS
codes in `ref_naics_code` (e.g. `115310e1`) are the structural counterpart — they encode exception
sub-categories that footnotes describe.

---

## 5. How FedProspect uses this

### Size-eligibility gating

The core question: **can this org legally bid a set-aside under this opportunity's NAICS?** An org
is size-eligible for a NAICS when its relevant measure is at or below that NAICS's size standard:

- Pull the opportunity's NAICS → look up `ref_sba_size_standard`.
- If `size_type = 'M'`: compare `organization.annual_revenue` (raw \$) against
  `size_standard * 1,000,000`.
- If `size_type = 'E'`: compare `organization.employee_count` against `size_standard`.
- Honor any attached footnote before treating the threshold as final.

### The org profile

Relevant columns on **`organization`** (in `60_prospecting.sql`):

| Column | Use |
|:-------|:----|
| `annual_revenue` `DECIMAL(18,2)` | Raw-dollar receipts for type-`M` comparisons. |
| `employee_count` `INT` | Head count for type-`E` comparisons. |
| `fiscal_year_end_month` `TINYINT UNSIGNED` | Which month the org's fiscal year ends — relevant because SBA receipts are an *average over multiple completed fiscal years*. |

NAICS the org operates in are stored in **`organization_naics`** (in `90_web_api.sql`):

| Column | Use |
|:-------|:----|
| `organization_id` | Owning org (FK, cascade delete). |
| `naics_code` `VARCHAR(11)` | A NAICS the org works in. |
| `is_primary` `VARCHAR(1)` | `Y`/`N` — the org's primary NAICS. |
| `size_standard_met` `VARCHAR(1)` | `Y`/`N` — whether the org currently qualifies as small for this NAICS. |

This join lets the app answer "which of our NAICS are we still small in?" and drive set-aside
targeting per code.

### Opportunity "outsized" warnings

When an org is browsing or scoring an opportunity whose NAICS size standard it *exceeds* (revenue
or headcount above the ceiling), the app should surface an **"outsized" warning** — the org is too
large to bid this NAICS as a small business, so small-business set-asides on it are off the table.

### The pWin set-aside factor

The probability-of-win (pWin) model includes a **set-aside factor**: opportunities whose set-aside
the org actually qualifies for (small-business size met *and* socioeconomic certs like WOSB/8(a)
present) score higher, because the competitive field is restricted to firms like the org. Size
eligibility per NAICS is an input to that factor.

### Important caveat — exclude affiliates / not legal advice

FedProspect's computed eligibility uses **only the org's own** `annual_revenue` / `employee_count`.
The real SBA rule **includes affiliate revenues/employees** (parent companies, commonly-controlled
firms, certain joint ventures), plus rules around averaging periods and recent acquisitions that we
do not model. Therefore:

- Computed size eligibility here is **indicative, not a legal determination**.
- The **UI must caveat this** wherever eligibility is shown (e.g. "Based on your entered revenue;
  excludes affiliate revenue — confirm your SBA size status independently").

---

## Related references

- [02-DATABASE-SCHEMA.md](02-DATABASE-SCHEMA.md) — full schema overview.
- [10-FEDERAL-IDENTIFIERS.md](10-FEDERAL-IDENTIFIERS.md) — UEI, CAGE, and other federal identifiers.
- [06-GLOSSARY.md](06-GLOSSARY.md) — domain terms (set-aside, WOSB, 8(a), etc.).

### Source files

| Artifact | Path |
|:---------|:-----|
| `ref_naics_code`, `ref_sba_size_standard`, `ref_naics_footnote` DDL | `fed_prospector/db/schema/tables/10_reference.sql` |
| `organization` (profile fields) DDL | `fed_prospector/db/schema/tables/60_prospecting.sql` |
| `organization_naics` DDL | `fed_prospector/db/schema/tables/90_web_api.sql` |
| Reference loader (hierarchy, size standards, footnotes) | `fed_prospector/etl/reference_loader.py` |
| Size-standard CSV | `workdir/converted/local database/data_to_import/naics_size_standards.csv` |
| Footnotes CSV | `workdir/converted/local database/data_to_import/footnotes.csv` |
