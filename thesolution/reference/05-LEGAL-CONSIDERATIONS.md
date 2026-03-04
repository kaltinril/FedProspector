# Legal Considerations

## Overview

All data sources used in this project are publicly available federal government APIs and datasets. However, each has specific terms of use, data handling requirements, and restrictions that must be followed.

---

## SAM.gov Terms of Use

### API Access Rules

1. **Automated scraping is prohibited**: "Automated data gathering, web scraping tools are prohibited." All data MUST be gathered through official APIs and extract downloads, never by scraping the website.

2. **API key requirements**:
   - Personal API keys: tied to individual SAM.gov accounts
   - System account keys: may be shared within your organization
   - Keys expire every 90 days and must be renewed
   - Never share personal API keys externally

3. **Rate limits are enforced**: Exceeding daily limits may result in temporary key suspension. The `BaseAPIClient` rate limit tracking prevents this.

### D&B (Dun & Bradstreet) Data Restrictions

SAM.gov contains Dun & Bradstreet data with strict limitations:

**D&B "Open Data" (Can store and use)**:
- Legal Business Name
- Street Address
- City
- State
- ZIP Code
- County
- Country

**Requirements for Open Data**:
- Must attribute D&B as the source if displayed
- Cannot redistribute in bulk

**D&B Restricted Data (Additional limitations)**:
- Cannot be used for commercial resale or marketing purposes
- Cannot be used for "customer identification, segmentation, or analysis"
- Use for internal prospecting is generally acceptable
- Do NOT use entity data for mass marketing campaigns

### PII (Personally Identifiable Information)

**Points of Contact data from the Entity API contains PII**:
- Names, titles, addresses
- (FOUO level: emails, phone numbers)

**Requirements**:
- Protect all downloaded PII with appropriate security controls
- Store in systems appropriate for the sensitivity level
- Securely destroy data no longer needed
- Do NOT use POC data for unsolicited marketing
- Public POC data (governmentBusinessPOC, electronicBusinessPOC) is available at the Public sensitivity level

### Data Sensitivity Levels

| Level | Content | Access Required |
|-------|---------|-----------------|
| Public | Names, UEI, addresses, business types, NAICS | Any API key |
| FOUO (CUI) | Hierarchy, security clearance, emails, phones | Federal System Account with "Read FOUO" |
| Sensitive (CUI) | Banking, SSN/TIN/EIN | Federal System Account with "Read Sensitive" + POST only |

**This project uses PUBLIC level data only** unless a federal system account is obtained.

### FOUO Data Restrictions

- Federal Hierarchy FOUO data "cannot be displayed or disseminated outside the U.S. Government unless directly associated with a Federal award record."
- Do not attempt to access FOUO endpoints without proper authorization

---

## USASpending.gov

- **Open public data** under the DATA Act
- No authentication required
- No documented redistribution restrictions
- API source code is open source (GitHub)
- Suitable for any analytical use

---

## FPDS (Federal Procurement Data System)

- **ATOM feed is public** - no account required
- **SOAP API** requires credentials
- Data is public federal procurement information
- No documented redistribution restrictions for public data

---

## GSA CALC+ API

- No authentication required
- Public data on awarded government contract rates
- No documented redistribution restrictions
- Data refreshed nightly

---

## Regulations.gov / Federal Register

- Public APIs
- Regulations.gov requires free API key from api.data.gov
- Federal Register requires no authentication
- Public government data, no special restrictions

---

## Key Legal Risk Areas

### 1. Storing POC Contact Information
- **Permitted**: Store public POC data from SAM.gov Entity API for legitimate business use (identifying contracting officers, teaming partners)
- **Not permitted**: Mass marketing emails to POCs harvested from SAM.gov
- **Recommendation**: Store POC data in `entity_poc` table. Use for targeted business development only.

### 2. D&B Data Fields
- **Permitted**: Store D&B Open Data (name, address) for internal use
- **Not permitted**: Build a product that resells or republishes D&B data
- **Recommendation**: This system is for internal prospecting, not a commercial data product. Compliant as designed.

### 3. Bulk Data Redistribution
- **Not permitted**: Build a commercial alternative to SAM.gov using their data
- **Permitted**: Internal database for your own business analysis and prospecting
- **Recommendation**: Keep the database internal. Do not expose it as a service to others.

### 4. Web Scraping
- **Not permitted**: Scraping SAM.gov, DSBS, SubNet, or any government website
- **Permitted**: Using official APIs and extract download endpoints
- **Recommendation**: All data gathering in this project uses official APIs. No scraping.

### 5. Data Retention
- **No specific retention limits** documented for most sources
- **Recommendation**: Keep data as long as it's useful. Archive old history records (> 1 year) to manage database size. Securely purge PII when no longer needed.

---

## Compliance Checklist

Before going live, verify:

- [ ] All data is gathered through official APIs (no web scraping)
- [ ] SAM.gov API key is properly managed (90-day renewal, not shared externally)
- [ ] Rate limits are tracked and never exceeded
- [ ] PII data (POC names, addresses) is stored securely
- [ ] D&B data is used only for internal analysis, not resold
- [ ] `.env` file with API keys is in `.gitignore` and not committed to version control
- [ ] FOUO/Sensitive endpoints are not accessed without proper authorization
- [ ] Database access is restricted to authorized team members
- [ ] Backup files containing PII are stored securely

---

## API Key Management

### SAM.gov API Key Lifecycle

```
Day 0:   Create/renew key at sam.gov
Day 1-76: Normal operation
Day 77:  14-day expiration warning
Day 83:  7-day expiration warning
Day 89:  1-day expiration warning
Day 90:  Key expires - all API calls will fail
```

### Key Renewal Process

1. Log in to SAM.gov
2. Navigate to account settings
3. Regenerate API key
4. Update `.env` file with new key
5. Restart any running scheduler jobs
6. Verify connectivity: `python main.py health status`

### Key Storage

- Store in `.env` file (never in source code)
- `.env` is in `.gitignore`
- Backup `.env` securely (encrypted, not in cloud storage without encryption)
- Document key holder and renewal responsibility
