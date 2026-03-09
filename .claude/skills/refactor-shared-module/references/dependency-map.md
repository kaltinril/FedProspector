# Shared Module Dependency Map

## db/connection.py (35 consumers)

**Path:** `fed_prospector/db/connection.py`
**Import pattern:** `from db.connection import get_connection`

### Consumers by category:

**Loaders (9):**
- `etl/opportunity_loader.py`
- `etl/awards_loader.py`
- `etl/subaward_loader.py`
- `etl/exclusions_loader.py`
- `etl/fedhier_loader.py`
- `etl/entity_loader.py`
- `etl/calc_loader.py`
- `etl/bulk_loader.py`
- `etl/usaspending_bulk_loader.py`

**ETL utilities (7):**
- `etl/staging_mixin.py`
- `etl/change_detector.py`
- `etl/load_manager.py`
- `etl/etl_utils.py`
- `etl/data_cleaner.py`
- `etl/health_check.py`
- `etl/db_maintenance.py`

**CLI modules (11):**
- `cli/admin.py`, `cli/database.py`, `cli/setup.py`, `cli/awards.py`
- `cli/calc.py`, `cli/entities.py`, `cli/exclusions.py`, `cli/fedhier.py`
- `cli/health.py`, `cli/opportunities.py`, `cli/spending.py`, `cli/subaward.py`

**API clients (1):** `api_clients/base_client.py`

**Other (7):** `etl/prospect_manager.py`, `etl/reference_loader.py`, `etl/scheduler.py`, `etl/schema_checker.py`, `etl/usaspending_loader.py`, `etl/demand_loader.py`

---

## config/settings.py (21 consumers)

**Path:** `fed_prospector/config/settings.py`
**Import pattern:** `from config import settings`

### Consumers:

**API clients (6):**
- `api_clients/base_client.py`, `api_clients/calc_client.py`
- `api_clients/sam_entity_client.py`, `api_clients/sam_extract_client.py`
- `api_clients/sam_opportunity_client.py`, `api_clients/usaspending_client.py`

**CLI modules (8):**
- `cli/database.py`, `cli/setup.py`, `cli/awards.py`, `cli/bulk_spending.py`
- `cli/entities.py`, `cli/exclusions.py`, `cli/opportunities.py`, `cli/subaward.py`

**ETL/DB (5):** `etl/opportunity_loader.py`, `etl/reference_loader.py`, `etl/health_check.py`, `etl/db_maintenance.py`, `db/connection.py`

**Config (1):** `config/logging_config.py`
**Schema (1):** `etl/schema_checker.py`

---

## etl/staging_mixin.py (8 consumers)

**Path:** `fed_prospector/etl/staging_mixin.py`
**Import pattern:** `from etl.staging_mixin import StagingMixin`

### Consumers (all inherit StagingMixin):
- `etl/opportunity_loader.py`
- `etl/awards_loader.py`
- `etl/subaward_loader.py`
- `etl/exclusions_loader.py`
- `etl/fedhier_loader.py`
- `etl/usaspending_loader.py`

**Dependencies:** staging_mixin itself imports `db/connection.py`

---

## etl/change_detector.py (9 consumers)

**Path:** `fed_prospector/etl/change_detector.py`
**Import pattern:** `from etl.change_detector import ChangeDetector`

### Consumers:
- `etl/opportunity_loader.py`, `etl/awards_loader.py`, `etl/subaward_loader.py`
- `etl/exclusions_loader.py`, `etl/fedhier_loader.py`, `etl/entity_loader.py`
- `etl/usaspending_loader.py`, `cli/entities.py`

---

## etl/load_manager.py (20 consumers)

**Path:** `fed_prospector/etl/load_manager.py`
**Import pattern:** `from etl.load_manager import LoadManager`

### Consumers:

**Loaders (11):**
- `etl/opportunity_loader.py`, `etl/awards_loader.py`, `etl/subaward_loader.py`
- `etl/exclusions_loader.py`, `etl/fedhier_loader.py`, `etl/entity_loader.py`
- `etl/calc_loader.py`, `etl/demand_loader.py`, `etl/bulk_loader.py`
- `etl/usaspending_bulk_loader.py`, `etl/usaspending_loader.py`

**CLI modules (8):**
- `cli/awards.py`, `cli/bulk_spending.py`, `cli/entities.py`, `cli/exclusions.py`
- `cli/fedhier.py`, `cli/opportunities.py`, `cli/spending.py`, `cli/subaward.py`

---

## etl/etl_utils.py (9 consumers)

**Path:** `fed_prospector/etl/etl_utils.py`
**Import pattern:** `from etl.etl_utils import parse_date, parse_decimal`

### Consumers:
- `etl/opportunity_loader.py`, `etl/awards_loader.py`, `etl/subaward_loader.py`
- `etl/exclusions_loader.py`, `etl/fedhier_loader.py`, `etl/entity_loader.py`
- `etl/calc_loader.py`, `etl/usaspending_bulk_loader.py`, `etl/usaspending_loader.py`

---

## api_clients/base_client.py (13 consumers)

**Path:** `fed_prospector/api_clients/base_client.py`
**Import pattern:** `from api_clients.base_client import BaseAPIClient, RateLimitExceeded`

### Consumers (all inherit BaseAPIClient):
- `api_clients/calc_client.py`
- `api_clients/sam_entity_client.py`
- `api_clients/sam_extract_client.py`
- `api_clients/sam_opportunity_client.py`
- `api_clients/sam_awards_client.py`
- `api_clients/sam_exclusions_client.py`
- `api_clients/sam_fedhier_client.py`
- `api_clients/sam_subaward_client.py`
- `api_clients/usaspending_client.py`

**CLI references (3):** `cli/entities.py`, `cli/fedhier.py`, `cli/opportunities.py`
