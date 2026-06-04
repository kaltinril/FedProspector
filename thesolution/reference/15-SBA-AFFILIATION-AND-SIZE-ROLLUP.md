# 15 — SBA Affiliation & Size Roll-Up

How a firm's SBA **small-business size** is determined when it has affiliates, and how that maps
to FedProspect's org↔entity links. The headline rule most people get wrong: SBA size is the
**combined total** of the firm *and all its affiliates* — **not** the largest single entity.

> **Scope note — indicative only, NOT legal advice.** This is a domain primer for building
> FedProspect features. SBA size determinations are fact-specific and made by SBA, not by software.
> Anything FedProspect computes here is *indicative*. **For any actual bid, confirm size status
> with counsel and/or SBA.** This doc paraphrases the CFR; the regulation text controls.

This is the affiliate side of the size question. For the per-NAICS size *standards* themselves
(the thresholds, `size_type`, the units), see [13-NAICS-SIZE-STANDARDS.md](13-NAICS-SIZE-STANDARDS.md),
which explicitly defers the affiliate-inclusion rule to this document.

---

## 1. The core rule — combined, not largest

Under **13 CFR 121.103(a)(6)**, in determining a concern's size, SBA counts the receipts or
employees of the concern **"and all of its affiliates."** The mechanics:

- **Receipts** — **13 CFR 121.104(d)(1)**: the concern's average annual receipts are computed by
  **ADDING** the concern's average annual receipts to the average annual receipts of **each**
  affiliate.
- **Employees** — **13 CFR 121.106**: the number of employees is likewise the concern's employees
  **plus** the employees of all affiliates, averaged over the relevant period.

So size = **the SUM of the firm + every affiliate**, compared as one combined total against the
NAICS threshold. It is **not** the largest single entity, and it is **not** measured per-entity.

### Worked example

A firm has its own receipts plus two affiliates:

| Entity | Avg annual receipts |
|:-------|--------------------:|
| Own firm | \$1M |
| Affiliate A | \$10M |
| Joint venture B | \$2M |
| **Combined (what SBA compares)** | **\$13M** |

The firm is sized at **\$13M combined** against the NAICS size standard — **not** at \$10M (the
largest) and **not** at \$1M (its own). If the NAICS threshold were \$12.5M, the combined firm is
**other-than-small**, even though every individual entity is under the threshold.

---

## 2. What creates affiliation

Affiliation is about **control**, not a tidy ownership percentage:

- **13 CFR 121.103(a)(1)** — affiliation exists when one concern controls or has the **power to
  control** another, or a third party controls or has the power to control both — **whether or not
  that power is actually exercised.**
- **13 CFR 121.103(a)(5)** — SBA considers the **"totality of the circumstances"** and **may find
  affiliation even where no single factor alone is sufficient** to establish it.

Affiliation is therefore **not** a simple ownership-threshold test. Common management, identity of
interest (e.g. family relationships, economic dependence), contractual relationships, newly
organized concerns, and other factors can each create affiliation. Two firms with no equity link at
all can still be affiliated.

---

## 3. How the two measures are calculated

### Receipts (`size_type = 'M'`)

- **Averaging period** — **13 CFR 121.104(c)(1)**: average annual receipts over the firm's **most
  recently completed five fiscal years**. (A three-year option exists **only for certain SBA loan
  programs** under **121.104(c)(4)** — **not** for federal procurement size determinations.)
- **What "receipts" means** — **13 CFR 121.104(a)**: total income **plus** cost of goods sold, as
  reported to the IRS, **excluding**:
  - net capital gains or losses,
  - taxes collected for and remitted to a taxing authority, and
  - **proceeds from transactions between a concern and its domestic or foreign affiliates.**

  That last exclusion matters for the roll-up: **inter-affiliate transactions must be excluded** so
  the same dollars aren't double-counted when you sum across the group.

### Employees (`size_type = 'E'`)

- **13 CFR 121.106** — average number of employees over the **preceding 24 completed calendar
  months**.
- **Full-time, part-time, temporary, and leased/PEO employees all count equally.** **Volunteers
  (unpaid) do not count.**

---

## 4. Joint ventures

**13 CFR 121.103(h)** — a joint venture may submit an offer as a small business **only if each
member of the JV is independently small** under the size standard for the specific contract's
NAICS. For its **own** size, a JV member counts its **proportionate share** of the JV's receipts /
employees.

So a "regular" JV does **not** let two small firms pool their way past the threshold — every member
must already be small on its own. (The exception to this is the mentor-protégé JV, next.)

---

## 5. Mentor-protégé exception — the key carve-out

This is the **one** case where size is effectively "based off one party." With an
**SBA-APPROVED** mentor-protégé agreement (MPA) under **13 CFR 125.9**:

- **13 CFR 121.103(b)(6)** — a protégé firm is **not affiliated** with its mentor solely because of
  the assistance provided under the MPA.
- **13 CFR 125.9(d)(1)(iii)** — a joint venture between a protégé and its SBA-approved mentor
  **"will qualify as a small business for any procurement... for which the protégé individually
  qualifies as small."**
- **13 CFR 125.9(d)(4)** — **no** finding of affiliation may be based **solely** on the MPA.

**Effect:** the mentor's size (often a large business) is **excluded** for that JV. The protégé-
mentor JV is small whenever the **protégé alone** is small under the contract's NAICS — the mentor's
revenue/headcount is left out of the roll-up.

**Critical qualifier:** this requires a **formal, SBA-approved** MPA. Informal "mentoring," a
handshake, or a private teaming relationship gets **no** exemption — those entities are evaluated
under the ordinary affiliation rules above.

---

## 6. Award dollars ≠ receipts

Do **not** feed USASpending / FPDS contract **obligation** amounts into a size calculation as if
they were receipts. "Receipts" is the specific accounting figure defined in **13 CFR 121.104(a)**
(total income + cost of goods sold, with the exclusions above) averaged over five fiscal years — a
firm's award obligations are neither the same number nor the same basis. Treat award dollars as a
*competition/market* signal, never as a size input.

---

## 7. How this maps to FedProspect

### `size_type` codes

In **`ref_sba_size_standard`** (loaded by `fed_prospector/etl/reference_loader.py`
`load_size_standards()` from `naics_size_standards.csv`, `TYPE` column → `size_type`):

| `size_type` | Meaning | Value units |
|:-----------:|:--------|:------------|
| `'M'` | Receipts-based standard | the value is in **\$ millions** |
| `'E'` | Employee-based standard | head count |

> **Historical bug:** the view `v_sba_size_standard_monitor` originally compared `'R'` for the
> revenue branch — a code that never appears in the data, so that branch was dead. Corrected to
> `'M'` in **Phase 133** (Task 4). All roll-up math uses `'M'` / `'E'`.

### Relationship types and their affiliation treatment

org↔entity links live in `organization_entity`; valid relationship codes are enforced by
`OrganizationEntityService.ValidRelationships`. How each maps to the size roll-up:

| Relationship | Affiliation treatment in the size roll-up |
|:-------------|:------------------------------------------|
| `SELF` | The hub org itself — **counts**. |
| `SISTER_SUBSIDIARY` *(planned)* | Commonly-controlled affiliate — **counts**. |
| `JV_PARTNER` | Regular joint-venture member — **counts**. |
| `TEAMING` | A teaming/subcontracting relationship — **does NOT create affiliation; excluded** from the size roll-up. |

> **`TEAMING` has a second, separate purpose.** Even though teaming links are excluded from the
> *size* roll-up, they still feed **"effective NAICS" / win-probability (pWin)** scoring — a
> different feature with a different question ("what can we credibly bid as a team?" vs. "are we
> small?"). Excluding teaming from affiliation does not remove it from those models.

> **Note on `SISTER_SUBSIDIARY`:** as of this writing the `ValidRelationships` set in
> `OrganizationEntityService.cs` contains only `SELF`, `JV_PARTNER`, `TEAMING`;
> `SISTER_SUBSIDIARY` is **planned** (Phase 133) and is the affiliate type the combined roll-up is
> built around.

### Mentor-protégé flag (planned)

An **SBA-approved** mentor-protégé JV must be **flagged per-link** so the roll-up **excludes the
mentor's size** for that JV (per §5). Without an approved-MPA flag on the link, FedProspect applies
the **conservative default — count it** (i.e. include the partner's size, which can only make the
firm look *less* small, never more).

### Data entry

FedProspect has **no data source for an external affiliate's receipts or headcount.** Affiliate
revenue / employee figures are **entered manually** per linked entity. The roll-up is only as good
as those manual inputs.

### Where it's implemented

The combined roll-up and the per-link MPA flag are implemented in **Phase 133, Task 6** — see
[133-LINKED-ENTITY-AGGREGATION-SISTER-SUBSIDIARY-SIZE-ROLLUP.md](../phases/completed/133-LINKED-ENTITY-AGGREGATION-SISTER-SUBSIDIARY-SIZE-ROLLUP.md).
It extends the single-org baseline `CompanyProfileService.CheckSizeEligibilityAsync` (Phase 129),
which (by design) considers only the org's own figures and excludes affiliates.

---

## 8. Sources

CFR text below was cross-checked against the Cornell Law eCFR mirror:

- 13 CFR 121.103 — Affiliation principles: <https://www.law.cornell.edu/cfr/text/13/121.103>
- 13 CFR 121.104 — Receipts (definition & averaging): <https://www.law.cornell.edu/cfr/text/13/121.104>
- 13 CFR 121.106 — Employees (definition & averaging): <https://www.law.cornell.edu/cfr/text/13/121.106>
- 13 CFR 125.9 — Mentor-protégé program: <https://www.law.cornell.edu/cfr/text/13/125.9>

> **Sourcing note:** the Cornell mirror is convenient but unofficial. For **compliance-grade** use,
> confirm against the **official eCFR** ([ecfr.gov](https://www.ecfr.gov/)) or
> **GovInfo** ([govinfo.gov](https://www.govinfo.gov/)), which are the authoritative sources.

---

## Related references

- [13-NAICS-SIZE-STANDARDS.md](13-NAICS-SIZE-STANDARDS.md) — the per-NAICS size **standards**,
  `size_type` (`'M'`/`'E'`), the unit gotcha, and the affiliate-exclusion caveat it defers here.
- [Phase 133 — Linked-Entity Aggregation & Size Roll-Up](../phases/completed/133-LINKED-ENTITY-AGGREGATION-SISTER-SUBSIDIARY-SIZE-ROLLUP.md) — the implementation (Task 6) and deferred mentor-protégé items.
- [06-GLOSSARY.md](06-GLOSSARY.md) — domain terms (set-aside, WOSB, 8(a), JV, etc.).
- [05-LEGAL-CONSIDERATIONS.md](05-LEGAL-CONSIDERATIONS.md) — broader legal/compliance posture.
