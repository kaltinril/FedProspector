# Phase 115B: Pricing Intelligence (Brainstorm Gap Analysis)

**Status:** PLANNED
**Priority:** TBD
**Source:** C:\git\brainstorm\docs\phases\ (phases 31-37)
**Dependencies:** GSA CALC+ data (loaded), USASpending awards (loaded), FPDS contracts (loaded), Phase 110 attachment intel (complete — scope summaries, labor categories, pricing structure extracted)

---

## Summary

The brainstorm project designed an entire pricing intelligence suite. We currently have raw GSA CALC+ labor rates loaded but no analysis layer on top. These features would help users price competitively.

---

## Overlap with Existing Features

| Idea | Status | What Exists |
|------|--------|-------------|
| Market Rate Heatmap | **NEW** — data ready | 230K+ GSA CALC+ rates in `gsa_labor_rate` table (labor_category, current_price, next_year_price, schedule, contractor_name, security_clearance). Zero analysis UI on top. |
| Price-to-Win Estimator | **NEW** — data ready | FPDS has 15+ years of `base_and_all_options` and `dollars_obligated` by NAICS/agency/vendor. Goldmine data, completely unused for pricing. |
| Bid Scenario Modeler | **NEW** | Pure frontend calculator — no new data needed |
| Rate Escalation Forecasting | **NEW** — needs BLS data | GSA CALC+ has `next_year_price` and `second_year_price` fields but no historical trend analysis or BLS integration |
| IGCE Reverse Engineering | **NEW** — data ready | Incumbent contract values via FPDS. SOW scope summaries + labor categories already extracted (Phase 110 complete). No estimate ensemble. |
| Subcontracting Cost Benchmarking | **NEW** — data ready | `sam_subaward` has `sub_amount`, prime/sub UEIs, NAICS, dates. Completely untapped for benchmarking. |
| Labor Category Normalization | **NEW** | 230K labor category strings loaded but highly inconsistent. No NLP pipeline. Would unlock features above. |

**Key insight:** The data foundation is strong — GSA CALC+, FPDS awards, subawards, and attachment-extracted intel (scope summaries, labor categories, pricing structure) are all loaded. `v_procurement_intelligence` already joins opportunities to FPDS contracts and USASpending awards with burn rate and contract ceiling. The gap is in the analysis/presentation layer.

---

## Features We Don't Have

### 1. Market Rate Heatmap

Interactive visualization: labor rates by category × agency × region. Shows GSA ceiling rates vs actual awarded rates. Drill-down to underlying contracts.

**Value:** "What are people actually getting paid for a Senior Java Developer at DHS in DC?"

**Source:** brainstorm phase-31

### 2. Price-to-Win Estimator

Given an opportunity, estimate the winning price:
- Find comparable past contracts (same NAICS, agency, scope)
- Adjust for inflation and scope differences
- For recompetes, anchor to incumbent's current contract value
- Output: probability distribution with percentile markers (25th, 50th, 75th)

**Source:** brainstorm phase-32

### 3. Bid Scenario Modeler

Interactive cost structure tool:
- Input: labor rates, fringe, overhead, G&A, fee %, ODCs, subs, travel
- Compute: total price at different fee/rate combinations
- Visualize: pWin-vs-profit tradeoff curve (lower price = higher pWin but lower margin)
- Expected value optimization: find the price that maximizes (pWin × profit)
- Side-by-side scenario comparison
- Monte Carlo simulation for risk analysis

**Source:** brainstorm phase-33

### 4. Rate Escalation Forecasting

Historical rate-of-change per labor category per region:
- Linear and exponential trend models
- 5-year projections with confidence bands
- BLS CPI/ECI benchmarking for validation
- **New data source needed:** Bureau of Labor Statistics APIs (ECI and CPI data)

**Source:** brainstorm phase-35

### 5. IGCE Reverse Engineering

Estimate the government's Independent Government Cost Estimate before bidding:
- 4 estimation methods: incumbent anchoring, comparable analysis, bottom-up SOW estimation, budget line-item extraction
- Weighted ensemble of all methods
- Retrospective accuracy tracking (compare estimate to actual award)

**Source:** brainstorm phase-36

### 6. Subcontracting Cost Benchmarking

Using our subaward data:
- Average/median sub values by NAICS and agency
- Pass-through rates (sub amount / prime amount)
- Fair-market-rate indicators — flag anomalously low subawards
- Useful for both primes (budgeting subs) and subs (negotiating rates)

**Source:** brainstorm phase-37

### 7. Labor Category Normalization

Government labor categories are wildly inconsistent ("Sr. Java Dev", "Senior Java Developer", "Java Developer III", "Software Engineer - Java" all mean the same thing). The brainstorm designed:
- NLP-powered mapping using sentence embeddings
- ~200 canonical categories in a 3-level hierarchy
- Alias tables for known synonyms
- Human review queue for low-confidence matches
- Applied to GSA CALC+ data to enable cross-contract rate comparison

**Source:** brainstorm phase-34

---

## New Data Sources Needed

| Source | Purpose | Notes |
|--------|---------|-------|
| Bureau of Labor Statistics (BLS) APIs | ECI and CPI data for rate escalation benchmarking | Free API, no auth needed |
| CBO Cost Estimates | Appropriations impact analysis | Web scraping, less critical |

---

## Implementation Notes

### Existing Foundation

These views and tables already provide building blocks:

| Asset | What It Does |
|-------|-------------|
| `v_procurement_intelligence` | Joins opportunity -> FPDS -> USASpending with burn rate, contract ceiling, bidder count, incumbent |
| `v_expiring_contracts` | Expiring contracts with burn rate, percent spent, incumbent health signals |
| `v_monthly_spend` | Monthly spending breakdown per award from `usaspending_transaction` |
| `document_intel_summary` | Extracted `scope_summary`, `labor_categories`, `pricing_structure`, `period_of_performance` per document |
| `fpds_contract.number_of_offers` | Historical bidder counts per contract — useful for pWin modeling |
| `fpds_contract.type_of_contract_pricing` | FFP vs T&M vs Cost-Plus classification |

### Build Order

- Features 1, 2, 6 can be built entirely on data we already have (GSA CALC+, awards, subawards)
- Feature 3 (bid scenario modeler) is a standalone calculator — no new data needed
- Feature 4 needs BLS data integration
- Feature 5 benefits from Phase 110 attachment intelligence (scope summaries, labor categories already extracted)
- Feature 7 (labor category normalization) is a data quality project that unlocks features 1-6
