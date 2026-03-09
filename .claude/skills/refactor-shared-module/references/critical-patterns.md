# Critical Patterns — Do NOT Break These

Each shared module has invariants that, if violated, cause **silent** failures (no exceptions, just wrong behavior).

## db/connection.py

### PooledMySQLConnection.autocommit Patch
```
INVARIANT: The monkey-patch on PooledMySQLConnection must exist.
WHY: mysql-connector-python's PooledMySQLConnection does NOT proxy the autocommit property.
     Without the patch, `conn.autocommit = True` is SILENTLY IGNORED.
IMPACT: StagingMixin's `_open_stg_conn()` sets autocommit=True on pooled connections.
        Without the patch, staging writes are NOT committed, and data is silently lost on rollback.
```

### Pool Default: autocommit=False
```
INVARIANT: Pool connections default to autocommit=False.
WHY: Main ETL connections need transactional batch commits.
     Staging connections explicitly override to autocommit=True.
IMPACT: If default changed to True, all batch commits become per-statement commits,
        breaking atomicity of multi-record loads.
```

---

## config/settings.py

### Module-Level Loading
```
INVARIANT: load_dotenv() runs at module level (import time).
WHY: All 21 consumers do `from config import settings` and access settings.VAR_NAME.
IMPACT: If changed to lazy loading, import-time access returns None silently.
```

### SAM Dual-Key Constants
```
INVARIANT: SAM_API_KEY, SAM_API_KEY_2, SAM_DAILY_LIMIT, SAM_DAILY_LIMIT_2 must all exist.
WHY: 4 SAM API clients + 6 CLI modules reference these by name.
IMPACT: Renaming or removing breaks API client constructors silently (default empty string).
```

---

## etl/staging_mixin.py

### Subclass Contract
```
INVARIANT: Subclasses must define _STG_TABLE (str), _STG_KEY_COLS (list), _extract_staging_key(raw) -> dict.
WHY: StagingMixin._insert_staging() reads these to build INSERT statements.
IMPACT: Missing _STG_TABLE -> AttributeError. Missing _STG_KEY_COLS -> empty key dict, no dedup.
```

### Autocommit=True on Staging Connection
```
INVARIANT: _open_stg_conn() sets conn.autocommit = True.
WHY: Staging writes must persist even if the main transaction rolls back.
     This is the entire point of staging — raw data is preserved for replay.
IMPACT: Without autocommit, staging rows are lost on main transaction rollback.
```

---

## etl/change_detector.py

### compute_hash() Field Order Independence
```
INVARIANT: Hash computation must be deterministic regardless of dict key order.
WHY: Records from different API calls may have keys in different order.
IMPACT: Non-deterministic hashing -> false "changed" detection on every load.
```

### get_existing_hashes() Return Format
```
INVARIANT: Returns dict of {key_value: hash_string}.
WHY: All 7 loaders look up old_hash = existing_hashes.get(record_key).
IMPACT: Changed return format breaks all loaders silently (always sees as "new").
```

---

## etl/load_manager.py

### start_load() Returns load_id
```
INVARIANT: Returns int load_id from etl_load_log insert.
WHY: All loaders pass load_id to staging, error logging, and complete_load.
IMPACT: Returning None -> FK violations in staging tables.
```

### complete_load() 5-Field Stats
```
INVARIANT: Accepts records_read, records_inserted, records_updated, records_unchanged, records_errored.
WHY: All loaders pass these by keyword; missing params default to 0.
IMPACT: Renamed params -> all loaders silently pass 0 counts.
```

---

## etl/etl_utils.py

### parse_date() Returns str or None
```
INVARIANT: Returns date string formatted as YYYY-MM-DD, or None.
WHY: Loaders store result directly in MySQL DATE columns.
IMPACT: Returning datetime object -> MySQL type error on INSERT.
```

### parse_decimal() Returns str or None
```
INVARIANT: Returns decimal as string (e.g., "1234.56"), or None.
WHY: Loaders store result directly in MySQL DECIMAL columns.
IMPACT: Returning float -> precision loss in monetary values.
```

---

## api_clients/base_client.py

### _sam_init_kwargs() Class Method
```
INVARIANT: Returns dict with base_url, api_key, source_name, max_daily_requests.
WHY: 4 SAM clients call super().__init__(**self._sam_init_kwargs(...)).
IMPACT: Missing key in returned dict -> TypeError in all SAM client constructors.
```

### Rate Counter: Only Counts 200 Responses
```
INVARIANT: _increment_rate_counter() called only on HTTP 200.
WHY: Failed requests (429, 500) should not consume daily quota.
IMPACT: Counting errors -> premature RateLimitExceeded, loads stop early.
```

### paginate() Generator Interface
```
INVARIANT: Yields page data (dict or list depending on results_key).
WHY: All paginated clients iterate with `for page_data in self.paginate(...)`.
IMPACT: Changed return type -> TypeError in all paginated searches.
```

## Testing After Refactoring

After ANY change to a shared module, run:
```bash
# Full test suite
cd fed_prospector && python -m pytest tests/ -v --tb=short

# Quick smoke test: verify all loaders import
python -c "
from etl.opportunity_loader import OpportunityLoader
from etl.awards_loader import AwardsLoader
from etl.entity_loader import EntityLoader
from etl.exclusions_loader import ExclusionsLoader
from etl.fedhier_loader import FedHierLoader
from etl.subaward_loader import SubawardLoader
from etl.usaspending_loader import USASpendingLoader
from etl.calc_loader import CalcLoader
print('All loaders import OK')
"

# Quick smoke test: verify all API clients import
python -c "
from api_clients.sam_opportunity_client import SAMOpportunityClient
from api_clients.sam_entity_client import SAMEntityClient
from api_clients.sam_awards_client import SAMAwardsClient
from api_clients.sam_exclusions_client import SAMExclusionsClient
from api_clients.sam_fedhier_client import SAMFedHierClient
from api_clients.sam_subaward_client import SAMSubawardClient
from api_clients.sam_extract_client import SAMExtractClient
from api_clients.usaspending_client import USASpendingClient
from api_clients.calc_client import CalcPlusClient
print('All API clients import OK')
"
```
