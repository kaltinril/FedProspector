# Federal Contracting Glossary

Reference for developers and AI agents working on this project. Definitions reflect standard federal acquisition terminology.

---

## 1. Procurement Process Terms

| Term | Definition | In Our System |
|------|-----------|---------------|
| **Solicitation** | A formal request from the government for proposals, quotes, or bids for goods or services. The primary document that contractors respond to. | `opportunity` table |
| **Scope of Work (SOW)** | The section within a solicitation that defines the specific tasks, deliverables, timeline, and requirements the contractor must fulfill. Also called Statement of Work or Performance Work Statement (PWS). | Part of opportunity description |
| **Sources Sought** | A market research notice where the government gauges industry interest and capability before deciding whether and how to solicit. Can help determine if a set-aside is appropriate. | `opportunity.type` field |
| **RFI (Request for Information)** | A pre-solicitation tool where the government asks industry about capabilities, market conditions, or technical approaches. Not a binding solicitation -- no award results from an RFI. | `opportunity.type` field |
| **RFP (Request for Proposal)** | A solicitation where the government requests detailed technical and cost proposals, evaluated on best value (not just price). | `opportunity.type` field |
| **RFQ (Request for Quote)** | A solicitation focused on price for well-defined requirements. Typically for commercial items or simplified acquisitions. | `opportunity.type` field |
| **Set-Aside** | A competition restriction that limits which businesses can bid. Not a contract type -- it is a filter (e.g., only WOSB-certified, only 8(a), only HUBZone). | `ref_set_aside_type`, `opportunity.set_aside_code` |
| **Contract** | A legally binding agreement between the government and a contractor specifying scope, price, period of performance, deliverables, and terms/conditions. | `fpds_contract` table |
| **Award** | The government's selection of a contractor and execution of a contract. | `fpds_contract` table |
| **IDIQ (Indefinite Delivery / Indefinite Quantity)** | A contract type that provides for an indefinite quantity of supplies or services within stated limits during a fixed period. Task orders are issued under it. | `fpds_contract.contract_type` |
| **Task Order / Delivery Order** | An individual order issued under an IDIQ contract for specific work. | `fpds_contract.idv_piid` |

---

## 2. People & Roles

| Term | Definition | In Our System |
|------|-----------|---------------|
| **Contracting Officer (CO/KO)** | The only government official with legal authority to enter into, administer, and terminate contracts. Posts solicitations and makes award decisions. | `contracting_officer` table (Phase 9) |
| **COR (Contracting Officer's Representative)** | The CO's designated technical representative who monitors day-to-day contract performance. Has no contracting authority -- serves as the liaison between the government and contractor. | Future field on `proposal` table |
| **Entity** | Any organization registered in SAM.gov. Registration makes them eligible to compete for and receive federal awards. Does not mean they have won anything. | `entity` table |
| **Prime Contractor** | The entity that holds the direct contract with the government. | `fpds_contract.vendor_uei` |
| **Subcontractor** | An entity that performs work under the prime contractor, not directly for the government. | `sam_subaward` table |

---

## 3. Organizations

| Term | Definition | In Our System |
|------|-----------|---------------|
| **Agency / Department** | A cabinet-level or independent federal organization (e.g., Department of Defense, NASA, GSA). | `opportunity.department_name`, `federal_organization` |
| **Sub-tier Agency / Bureau** | A component within a department (e.g., Army Corps of Engineers within DoD). | `opportunity.sub_tier`, `federal_organization` hierarchy |
| **Contracting Office** | The specific office within an agency that manages procurements. | `opportunity.office`, `opportunity.contracting_office_id` |
| **Requiring Activity / End User** | The organizational unit that needs the goods or services. Informally called the "customer." Not always the same as the contracting office. | Not directly tracked; inferred from sub-tier/office |

---

## 4. Identifiers

| Identifier | Full Name | Format | Issued By | In Our System |
|-----------|-----------|--------|-----------|---------------|
| **UEI** | Unique Entity Identifier | 12-character alphanumeric | SAM.gov | `entity.uei_sam` (primary key) |
| **CAGE Code** | Commercial and Government Entity Code | 5-character alphanumeric | Defense Logistics Agency (DLA) | `entity.cage_code` |
| **NCAGE Code** | NATO CAGE Code | Same format as CAGE, for non-U.S. entities | NATO systems | `entity.cage_code` (same field) |
| **NAICS Code** | North American Industry Classification System | Up to 6 digits | U.S. Census Bureau | `ref_naics_code`, `entity_naics`, `opportunity.naics_code` |
| **PSC Code** | Product Service Code | Up to 4 characters | GSA | `ref_psc_code`, `entity_psc`, `fpds_contract.psc_code` |
| **SIC Code** | Standard Industrial Classification | 4 digits | OMB (deprecated) | Not tracked (replaced by NAICS) |
| **PIID** | Procurement Instrument Identifier | Varies (e.g., `W912DY-24-C-0001`) | Contracting office | `fpds_contract.contract_id` |
| **Solicitation Number** | Solicitation Number | Varies | Contracting office | `opportunity.solicitation_number` |
| **DODAAC** | Department of Defense Activity Address Code | 6-character alphanumeric | DLA | `entity.dodaac` |
| **EIN/TIN** | Employer Identification Number / Taxpayer Identification Number | 9 digits | IRS | Not tracked (compliance risk) |
| **CGAC** | Common Government-wide Accounting Classification | 3 digits | Treasury / OMB | `federal_organization.cgac` |

Notes on identifiers:
- UEI replaced the DUNS number (previously issued by Dun & Bradstreet) in April 2022.
- CAGE codes are auto-assigned after SAM registration for U.S. entities.
- Each solicitation is assigned a NAICS code that determines which size standard applies.
- PSC describes *what* the government is buying; NAICS describes *who* sells it.
- Solicitation number links a solicitation to its resulting contract.

---

## 5. Certifications & Set-Aside Types

| Code | Full Name | Description |
|------|-----------|-------------|
| **WOSB** | Women-Owned Small Business | A small business that is at least 51% owned and controlled by one or more women. Must be certified through SBA. |
| **EDWOSB** | Economically Disadvantaged Women-Owned Small Business | A WOSB whose women owners are also economically disadvantaged. Eligible for additional sole-source and set-aside contracts. |
| **8(a)** | SBA 8(a) Business Development Program | A 9-year program for small businesses owned by socially and economically disadvantaged individuals. Participants can receive sole-source contracts up to certain thresholds. |
| **HUBZone** | Historically Underutilized Business Zone | A small business that maintains its principal office in and at least 35% of its employees reside in a HUBZone. Certified by SBA. |
| **SDVOSB** | Service-Disabled Veteran-Owned Small Business | A small business owned and controlled by one or more service-disabled veterans. Certified by SBA (transferred from VA in January 2023). |
| **VOSB** | Veteran-Owned Small Business | A small business owned and controlled by one or more veterans. Certified by SBA. |
| **SDB** | Small Disadvantaged Business | A small business owned and controlled by one or more socially and economically disadvantaged individuals. Automatic qualification for businesses in the 8(a) program. |

Stored in `ref_set_aside_type` and `ref_business_type` / `entity_business_type`.

---

## 6. Key Systems

| System | URL | Purpose | Our Integration |
|--------|-----|---------|----------------|
| **SAM.gov** | https://sam.gov | Entity registration, opportunity posting, exclusions, federal hierarchy | Entity API, Opportunity API, Exclusions API, Federal Hierarchy API |
| **FPDS** | https://fpds.gov | Federal Procurement Data System. Official record of all federal contract actions. | SAM Contract Awards API (which pulls from FPDS) |
| **USASpending.gov** | https://usaspending.gov | Public transparency site for all federal spending. Richer award and transaction detail. | USASpending Transactions API |
| **GSA CALC+** | https://buy.gsa.gov/pricing | GSA labor rate benchmarks (formerly CALC -- Contract-Awarded Labor Category tool). | GSA CALC+ API |
| **beta.SAM.gov** | N/A | Legacy portal name for SAM.gov. Retired. Same system. | N/A |

---

## API Types in This System

Two distinct uses of "API" appear throughout the project documentation. Always use the qualified terms below to avoid confusion.

| Term | What It Is | Technology | Rate Limited? | Called By |
|------|-----------|-----------|---|---|
| **Vendor API** | External government data sources: SAM.gov (v1–v4), USASpending.gov, GSA CALC+ | REST (various auth methods) | Yes — SAM.gov key 1: 10/day, key 2: 1,000/day | Python `load` commands only |
| **App API** | FedProspect's own C# backend REST API | ASP.NET Core (.NET 10), 59 endpoints, 13 controllers | No (local deployment) | React frontend UI (Phases 20-70) |

**The architectural rule**: Vendor APIs populate the local MySQL database via the Python ETL pipeline. The App API reads from that local database and exposes data to the UI. The App API never calls Vendor APIs.

**Data flow**: `Vendor APIs → Python ETL → MySQL → App API → React UI`
