"""Environment-based configuration. Never hardcode secrets."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Database
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_NAME = os.getenv("DB_NAME", "fed_contracts")
DB_USER = os.getenv("DB_USER", "fed_app")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "10"))

# SAM.gov API
SAM_API_KEY = os.getenv("SAM_API_KEY", "")
SAM_API_KEY_2 = os.getenv("SAM_API_KEY_2", "")
SAM_API_BASE_URL = "https://api.sam.gov"
SAM_DAILY_LIMIT = int(os.getenv("SAM_DAILY_LIMIT", "10"))
SAM_DAILY_LIMIT_2 = int(os.getenv("SAM_DAILY_LIMIT_2", "1000"))

# SAM.gov API key creation dates (for expiration tracking, ISO format YYYY-MM-DD)
SAM_API_KEY_CREATED = os.getenv("SAM_API_KEY_CREATED", "")
SAM_API_KEY_2_CREATED = os.getenv("SAM_API_KEY_2_CREATED", "")
SAM_KEY_EXPIRY_DAYS = 90

# SAM.gov Federal Hierarchy API
SAM_FED_HIERARCHY_URL = "https://api.sam.gov/prod/federalorganizations/v1/orgs"

# SAM.gov Exclusions API
SAM_EXCLUSIONS_URL = "https://api.sam.gov/entity-information/v4/exclusions"

# GSA CALC API (no auth needed)
CALC_API_BASE_URL = "https://api.gsa.gov/acquisition/calc/v3/api"

# USASpending API (no auth needed)
USASPENDING_API_BASE_URL = "https://api.usaspending.gov"

# SAM.gov Contract Awards API (replacement for FPDS)
SAM_CONTRACT_AWARDS_URL = "https://api.sam.gov/contract-awards/v1/search"

# Default awards filters (used when no --naics/--set-aside specified)
DEFAULT_AWARDS_NAICS = os.getenv(
    "DEFAULT_AWARDS_NAICS",
    "336611,488190,519210,541219,541330,541511,541512,541513,541519,"
    "541611,541612,541613,541690,541990,561110,561210,561510,561990,"
    "611430,611710,621111,621399,624190,812910"
)
DEFAULT_AWARDS_SET_ASIDES = os.getenv("DEFAULT_AWARDS_SET_ASIDES", "8A,WOSB,SBA")

# SAM.gov Subaward Reporting API
SAM_SUBAWARD_URL = "https://api.sam.gov/prod/contract/v1/subcontracts/search"

# FPDS ATOM Feed - DEPRECATED: ezSearch decommissioned Feb 24, 2026;
# ATOM feed sunsetting later FY2026. Use SAM_CONTRACT_AWARDS_URL instead.
FPDS_ATOM_BASE_URL = "https://www.fpds.gov/dbsight/FEEDS/ATOM"

# Bureau of Labor Statistics API (free, optional registration key)
BLS_API_BASE_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
BLS_API_KEY = os.getenv("BLS_API_KEY", "")
BLS_DAILY_LIMIT = int(os.getenv("BLS_DAILY_LIMIT", "500"))

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", str(PROJECT_ROOT / "data")))
DOWNLOAD_DIR = DATA_DIR / "downloads"
LOG_DIR = DATA_DIR / "logs"
ATTACHMENT_DIR = Path(os.getenv("ATTACHMENT_DIR", str(DATA_DIR / "attachments"))).resolve()

# Reference data paths (relative to project root's parent = fedProspect/)
REPO_ROOT = PROJECT_ROOT.parent
WORKDIR = REPO_ROOT / "workdir" / "converted"
REF_DATA_DIR = WORKDIR / "local database" / "data_to_import"
OLD_RESOURCES = REPO_ROOT / "OLD_RESOURCES"

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
