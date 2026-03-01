# USASpending.gov Transactions API - Research Notes

Researched: 2026-02-28

## Endpoint
- **URL**: `POST https://api.usaspending.gov/api/v2/transactions/`
- **Auth**: None required
- **Rate Limit**: None documented (unlimited)

## Request Body
```json
{
  "award_id": "CONT_AWD_N0001917C0015_9700_-NONE-_-NONE-",
  "page": 1,
  "limit": 5000,
  "sort": "action_date",
  "order": "desc"
}
```

**Parameters:**
- `award_id` (string, required): Generated unique award ID format `CONT_AWD_{...}` or `ASST_AWD_{...}`
- `page` (int, optional): 1-based page number (default 1)
- `limit` (int, optional): 1-5000 records per page (default 10)
- `sort` (string, optional): Sort field (default `action_date`)
- `order` (string, optional): `asc` or `desc` (default `desc`)

## Response Structure
```json
{
  "results": [
    {
      "id": "transaction_internal_id",
      "type": "C",
      "type_description": "Delivery Order",
      "action_date": "2025-06-15",
      "action_type": "A",
      "action_type_description": "New",
      "modification_number": "00",
      "description": "SUPPLY CHAIN SECURITY SERVICES",
      "federal_action_obligation": 125000.00,
      "face_value_loan_guarantee": null,
      "original_loan_subsidy_cost": null,
      "cfda_number": null
    }
  ],
  "page_metadata": {
    "page": 1,
    "next": 2,
    "previous": null,
    "hasNext": true,
    "hasPrevious": false,
    "total": 47,
    "limit": 10
  }
}
```

## Transaction Fields
| Field | Type | Purpose |
|-------|------|---------|
| `id` | string | Unique transaction ID |
| `type` | string | Type code: A=BPA Call, B=Purchase Order, C=Delivery Order, D=Definitive Contract |
| `type_description` | string | Human-readable type |
| `action_date` | date | YYYY-MM-DD format |
| `action_type` | string | A=New, C=Modification, E=Termination, etc. |
| `action_type_description` | string | Human-readable action |
| `modification_number` | string | null for new, "00"/"01"/"02" for mods |
| `description` | string | Full text description |
| `federal_action_obligation` | decimal | Dollar amount committed/obligated |
| `face_value_loan_guarantee` | decimal | For loan awards only |
| `original_loan_subsidy_cost` | decimal | For loan awards only |
| `cfda_number` | string | For grants/assistance only |

## Pagination
- Page-based (1-indexed), NOT offset-based
- Check `page_metadata.hasNext` to continue
- Max 5000 per page

## How to Look Up Award ID from Solicitation Number
Two-step process:

**Step 1**: Search by solicitation via existing `search_awards()`:
```json
POST https://api.usaspending.gov/api/v2/search/spending_by_award/
{
  "filters": {
    "award_type_codes": ["A", "B", "C", "D"],
    "keywords": ["W911NF-25-R-0001"]
  },
  "fields": ["Award ID", "generated_unique_award_id", "Recipient Name"],
  "limit": 10,
  "page": 1
}
```

**Step 2**: Extract `generated_unique_award_id` from results, use for transactions endpoint.

Alternative: Use existing `usaspending_client.search_incumbent()` which already does keyword-based search and returns award IDs.

## Burn Rate Calculation
With transaction data, burn rate can be calculated as:
- **Simple**: `total_obligation / months_elapsed` (from usaspending_award table, no transactions needed)
- **Detailed**: Sum `federal_action_obligation` by month from transactions → monthly spending timeline
- **Cumulative**: Running sum of `federal_action_obligation` ordered by `action_date` → obligation curve

## Integration Notes
- Existing `USASpendingClient` already uses POST-based search pattern
- Already has `self.post()` method from `BaseAPIClient`
- Already has pagination patterns in `search_awards_all()`
- New methods just need to call `/api/v2/transactions/` with similar pattern
