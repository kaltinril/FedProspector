# FedProspect Mission Statement

## Mission

FedProspect gives small federal contractors the competitive intelligence they need to find, evaluate, and win government contracts. By aggregating data from 10+ government sources into a single actionable platform, we eliminate the manual research burden and surface opportunities that firms would otherwise miss.

## Who We Serve

Small businesses pursuing federal contracts, with a focus on WOSB (Women-Owned Small Business) and 8(a) certified firms. These companies face a common set of problems:

- **Information is scattered** across SAM.gov, USASpending, FPDS, and GSA portals with no unified view.
- **Competitive intelligence is invisible** — free government sites show what was awarded, not who is vulnerable or how to win.
- **Recompetes surface too late** — by the time a solicitation posts, incumbents have months of positioning advantage.
- **Capture management is ad hoc** — tracking pursuits in spreadsheets or generic CRMs breaks down at scale.

## Core Value Proposition

FedProspect delivers intelligence that does not exist on free government websites:

- **Incumbent analysis** — burn rates, subcontractor networks, contract performance history.
- **Probability-of-win scoring** — algorithmic pWin based on the firm's certifications, past performance, and competitive landscape.
- **Expiring contract detection** — identify recompete targets months before resolicitation, when positioning matters most.
- **Market share analysis** — understand who dominates a NAICS code and where the gaps are.
- **Qualification checks** — instant validation of eligibility (set-asides, certifications, NAICS alignment) before investing capture effort.

## How It Works

**Data.** Automated ETL pipelines pull daily from SAM.gov, USASpending, FPDS, GSA CALC+, and federal hierarchy sources. 500K+ contractor entities and 100K+ opportunities are normalized, deduplicated, and indexed in a local intelligence layer.

**Analysis.** The system matches opportunities to each organization's NAICS codes and certifications, scores probability of win, flags expiring contracts for recompete targeting, and runs competitive analysis against incumbents.

**Action.** Matched opportunities flow into a Kanban capture pipeline where teams collaborate on pursuits from discovery through bid submission. Saved search alerts and daily refreshes ensure nothing is missed.

## Competitive Advantage

| Capability | Free Gov Sites | GovWin IQ / Deltek | FedProspect |
|---|---|---|---|
| Opportunity search | Yes | Yes | Yes |
| Incumbent burn rate analysis | No | Partial | Yes |
| pWin scoring | No | Manual | Automated |
| Recompete detection before solicitation | No | Limited | Yes |
| WOSB/8(a) eligibility validation | No | No | Built-in |
| Integrated capture pipeline | No | Separate tool | Native |
| Multi-team collaboration with data isolation | N/A | Enterprise-tier | Standard |
| Sub-second search across 100K+ opportunities | Slow | Yes | Yes |

FedProspect replaces the prior Salesforce approach that failed at scale (CPU and transaction limits at 1M+ records) with a purpose-built stack: Python ETL for data acquisition, MySQL for fast querying, C# API for multi-tenant access control, and React UI for the capture workflow.
