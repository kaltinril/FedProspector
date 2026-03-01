# Data Architecture - Procurement Intelligence Linking Chain

## 1. Purpose

This document maps the federal procurement lifecycle to the database schema, showing how tables link together and which data sources answer common intelligence questions. It saves AI agents and developers from exploring the full schema — read this file to know where every data point lives.

---

## 2. Procurement Lifecycle Linking Chain

```
                    solicitation_number
RFI (presolicitation) ──── ? ────► Solicitation (RFP)
    notice_id (unique)              notice_id (unique)
    type = 'presolicitation'        type = 'solicitation'
    NO LINK FIELD EXISTS            solicitation_number ──┐
                                    award_number ───────┐ │
                                                        │ │
                    ┌───────────────────────────────────┘ │
                    ▼                                     │
            fpds_contract                                 │
                contract_id (PIID) ◄── award_number       │
                vendor_uei                                │
                number_of_offers (bidder count)           │
                dollars_obligated                         │
                solicitation_number ◄─────────────────────┘

            usaspending_award
                piid ◄── contract_id (PIID)
                solicitation_identifier ◄── solicitation_number
                recipient_uei ◄── vendor_uei
                total_obligation
                    │
                    ▼
            usaspending_transaction
                award_id (FK)
                action_date + federal_action_obligation
                (burn rate = sum over time)

            sam_entity (incumbent profile)
                uei_sam ◄── vendor_uei / recipient_uei
                entity_sba_certification (WOSB, 8a status)
                entity_naics, entity_business_type
```

---

## 3. Cross-Table Linking Fields

| From Table | Field | To Table | Field | Notes |
|------------|-------|----------|-------|-------|
| sam_opportunity | award_number | fpds_contract | contract_id | PIID link (post-award only) |
| sam_opportunity | solicitation_number | fpds_contract | solicitation_number | Direct match |
| sam_opportunity | solicitation_number | usaspending_award | solicitation_identifier | Direct match |
| sam_opportunity | awardee_uei | sam_entity | uei_sam | Awardee lookup |
| fpds_contract | contract_id | usaspending_award | piid | PIID match |
| fpds_contract | vendor_uei | sam_entity | uei_sam | Awardee entity |
| usaspending_award | recipient_uei | sam_entity | uei_sam | Incumbent entity |
| usaspending_award | id | usaspending_transaction | award_id | Transaction detail |
| fpds_contract | contracting_office_id | federal_organization | fh_org_id | Org hierarchy (note: may need mapping) |
| sam_opportunity | contracting_office_id | federal_organization | fh_org_id | Org hierarchy |
| opportunity_relationship | parent_notice_id | sam_opportunity | notice_id | Manual RFI-to-RFP link |
| opportunity_relationship | child_notice_id | sam_opportunity | notice_id | Manual RFI-to-RFP link |

---

## 4. Intelligence Question to Data Source Mapping

| Question | Primary Source | Key Fields | Availability | Notes |
|----------|---------------|------------|--------------|-------|
| Award history | `fpds_contract` + `usaspending_award` | contract_id, dollars_obligated, date_signed, modifications | Ad-hoc API call | Search by solicitation_number or PIID |
| Number of bidders | `fpds_contract` | `number_of_offers`, `extent_competed` | Post-award only | N/A for RFIs. Field only populated after contract award. |
| Security clearance | NOT AVAILABLE VIA API | -- | Manual only | Lives in SOW/PWS document attachments on SAM.gov. GSA CALC+ has clearance data on labor rates (inferential only). |
| Burn rate | `usaspending_transaction` | `action_date`, `federal_action_obligation` | Ad-hoc API call | Aggregate by month. Shows obligations (committed), not expenditures (paid). |
| Incumbent info | `usaspending_award` then `sam_entity` | `recipient_uei` then entity profile | Ad-hoc API call | Chain: USASpending finds awardee UEI, SAM Entity gives full company profile + certifications |
| RFI to RFP link | `opportunity_relationship` | `parent_notice_id`, `child_notice_id` | Manual entry only | SAM.gov API has NO relational field. Users must link manually or business provides the solicitation number. |

---

## 5. Known Data Gaps

| Data Point | Why Not Available | Workaround |
|------------|-------------------|------------|
| Security clearance requirements | Not in any SAM.gov, FPDS, or USASpending API field | Check SOW/PWS on SAM.gov manually; GSA CALC+ labor rates have clearance levels (inferential) |
| RFI to RFP linking | SAM.gov Opportunity API has no parent/child fields | Manual linking via `opportunity_relationship` table; or business provides the solicitation number |
| Opportunity description text | `description` field is a URL, not text; full text requires System Account | User visits SAM.gov link; use title + NAICS to infer scope |
| Real-time contract expenditures | Only obligation data (committed $) is public | USASpending transaction timeline shows obligations over time |
| RFP attachments (SOW, PWS) | Requires authenticated download from SAM.gov | User downloads manually from SAM.gov |
| Entity facility clearance | CUI/FOUO data -- requires System Account access | Not available via public API |

---

## 6. Key Views

**`v_procurement_intelligence`** -- Joins opportunity to fpds_contract to usaspending_award for a given solicitation. Returns award history, bidder count, burn rate, incumbent in one query.

**`v_incumbent_profile`** -- Given a UEI, returns entity profile + active SBA certifications + past contract count + total obligated.

---

## 7. API Data Sources for Ad-Hoc Lookups

| API | Client Class | Key Methods | What It Provides |
|-----|-------------|-------------|-----------------|
| SAM Opportunity | `sam_opportunity_client.py` | `search_opportunities(solnum=...)` | Opportunity details, award info |
| SAM Awards (FPDS) | `sam_awards_client.py` | `search_by_solicitation(piid)`, `search_by_awardee(uei)` | Contract awards, bidder count, vendor |
| USASpending | `usaspending_client.py` | `search_incumbent(sol_num)`, `get_award_transactions(id)` | Award amounts, burn rate, incumbent |
| SAM Entity | `sam_entity_client.py` | `get_entity_by_uei(uei)` | Company profile, certifications |
| SAM Exclusions | `sam_exclusions_client.py` | `check_entity(uei)` | Debarment/exclusion status |
| SAM Subaward | `sam_subaward_client.py` | `search_by_prime(uei)` | Subcontractors, teaming partners |
| GSA CALC+ | `calc_client.py` | `search_rates_all(keyword)` | Labor rates with security clearance levels |

---

## 8. Mermaid ERD (Procurement Intelligence Subset)

```mermaid
erDiagram
    sam_opportunity ||--o| fpds_contract : "award_number = contract_id"
    sam_opportunity ||--o| usaspending_award : "solicitation_number = solicitation_identifier"
    sam_opportunity ||--o| opportunity_relationship : "notice_id (parent or child)"
    fpds_contract ||--o| usaspending_award : "contract_id = piid"
    fpds_contract }o--|| sam_entity : "vendor_uei = uei_sam"
    usaspending_award }o--|| sam_entity : "recipient_uei = uei_sam"
    usaspending_award ||--|{ usaspending_transaction : "id = award_id"
    sam_entity ||--|{ entity_sba_certification : "uei_sam"
    sam_entity ||--|{ entity_naics : "uei_sam"
    sam_entity ||--|{ entity_business_type : "uei_sam"
    sam_entity ||--|{ fpds_contract : "uei_sam = vendor_uei"

    sam_opportunity {
        varchar notice_id PK
        varchar solicitation_number
        varchar award_number
        varchar awardee_uei
        varchar type
        varchar naics_code
        varchar contracting_office_id
    }

    fpds_contract {
        varchar contract_id PK
        varchar solicitation_number
        varchar vendor_uei
        varchar vendor_name
        int number_of_offers
        decimal dollars_obligated
        decimal base_and_all_options
        varchar contracting_office_id
    }

    usaspending_award {
        int id PK
        varchar piid
        varchar solicitation_identifier
        varchar recipient_uei
        varchar recipient_name
        decimal total_obligation
        decimal base_and_all_options_value
    }

    usaspending_transaction {
        bigint id PK
        int award_id FK
        date action_date
        decimal federal_action_obligation
    }

    sam_entity {
        varchar uei_sam PK
        varchar legal_business_name
        varchar primary_naics
        char registration_status
    }

    opportunity_relationship {
        int id PK
        varchar parent_notice_id FK
        varchar child_notice_id FK
        varchar relationship_type
    }
```
