"""CLI command for verifying system prerequisites."""

import importlib
import importlib.util
import os
import shutil
import sys

import click

from config import settings


REQUIRED_PACKAGES = [
    "bcrypt",
    "mysql.connector",
    "click",
    "dotenv",
    "requests",
]

PACKAGE_DISPLAY_NAMES = {
    "mysql.connector": "mysql-connector-python",
    "dotenv": "python-dotenv",
}

REQUIRED_ENV_KEYS = [
    "DB_HOST",
    "DB_PORT",
    "DB_NAME",
    "DB_USER",
    "DB_PASSWORD",
    "SAM_API_KEY",
]


def _pass(msg):
    click.echo(f"[PASS] {msg}")


def _fail(msg, fix=None):
    click.echo(f"[FAIL] {msg}")
    if fix:
        click.echo(f"       Fix: {fix}")


def _check_python_version():
    """Check 1: Python version >= 3.14."""
    vi = sys.version_info
    version_str = f"{vi.major}.{vi.minor}.{vi.micro}"
    if (vi.major, vi.minor) >= (3, 14):
        _pass(f"Python {version_str} (>= 3.14 required)")
        return True
    _fail(
        f"Python {version_str} found (>= 3.14 required)",
        fix="Install Python 3.14 or newer from https://www.python.org/downloads/",
    )
    return False


def _check_packages():
    """Check 2: Required pip packages installed."""
    missing = []
    for pkg in REQUIRED_PACKAGES:
        if importlib.util.find_spec(pkg) is None:
            display = PACKAGE_DISPLAY_NAMES.get(pkg, pkg)
            missing.append(display)
    if not missing:
        _pass("All required packages installed")
        return True
    _fail(
        f"Missing packages: {', '.join(missing)}",
        fix=f"pip install {' '.join(missing)}",
    )
    return False


def _check_env_file():
    """Check 3: .env file exists with required keys."""
    env_path = settings.PROJECT_ROOT / ".env"
    if not env_path.exists():
        _fail(
            ".env file not found",
            fix=f"Create {env_path} with keys: {', '.join(REQUIRED_ENV_KEYS)}",
        )
        return False

    missing_keys = []
    for key in REQUIRED_ENV_KEYS:
        val = os.getenv(key)
        if not val:
            missing_keys.append(key)

    if not missing_keys:
        _pass(".env file found with all required keys")
        return True
    _fail(
        f".env file missing key: {', '.join(missing_keys)}",
        fix=f"Add {', '.join(f'{k}=your_value' for k in missing_keys)} to {env_path}",
    )
    return False


def _check_mysql_binary():
    """Check 4: MySQL binary found."""
    mysql_bin_dir = os.getenv("MYSQL_BIN_DIR")
    if mysql_bin_dir:
        for name in ("mysqld.exe", "mysqld"):
            candidate = os.path.join(mysql_bin_dir, name)
            if os.path.isfile(candidate):
                _pass(f"MySQL binary found at {candidate}")
                return True

    path_result = shutil.which("mysqld")
    if path_result:
        _pass(f"MySQL binary found at {path_result}")
        return True

    if mysql_bin_dir:
        _fail(
            f"MySQL binary not found in MYSQL_BIN_DIR ({mysql_bin_dir}) or on PATH",
            fix="Set MYSQL_BIN_DIR to the directory containing mysqld, or add it to PATH",
        )
    else:
        _fail(
            "MySQL binary not found on PATH (MYSQL_BIN_DIR not set)",
            fix="Set MYSQL_BIN_DIR env var or add mysqld to PATH",
        )
    return False


def _check_mysql_connection():
    """Check 5: MySQL server reachable."""
    try:
        from db.connection import get_connection

        conn = get_connection()
        conn.close()
        _pass(f"MySQL server reachable at {settings.DB_HOST}:{settings.DB_PORT}")
        return True
    except Exception as e:
        _fail(
            f"Cannot connect to MySQL at {settings.DB_HOST}:{settings.DB_PORT}",
            fix=f"Start MySQL and verify credentials in .env ({e})",
        )
        return False


def _check_database_exists():
    """Check 6: Database exists (SELECT 1 succeeds)."""
    try:
        from db.connection import get_connection

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        conn.close()
        _pass(f"Database '{settings.DB_NAME}' exists and is accessible")
        return True
    except Exception as e:
        _fail(
            f"Database '{settings.DB_NAME}' not accessible",
            fix=f"Create the database: CREATE DATABASE {settings.DB_NAME} ({e})",
        )
        return False


def _check_schema_tables():
    """Check 7: Schema tables present (expect ~56)."""
    try:
        from db.connection import get_connection

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = %s",
            (settings.DB_NAME,),
        )
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()

        if count >= 50:
            _pass(f"{count} tables found in schema (expected ~56)")
            return True
        elif count > 0:
            _fail(
                f"Only {count} tables found (expected ~56)",
                fix="Run: python main.py build-database",
            )
            return False
        else:
            _fail(
                "No tables found in database",
                fix="Run: python main.py build-database",
            )
            return False
    except Exception as e:
        _fail(f"Could not query schema tables ({e})")
        return False


def _check_quality_rules():
    """Check 7b: Quality rules seeded in etl_data_quality_rule."""
    try:
        from db.connection import get_connection

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM etl_data_quality_rule")
        rule_count = cursor.fetchone()[0]
        cursor.close()
        conn.close()

        if rule_count > 0:
            _pass(f"Quality rules seeded ({rule_count} rules)")
            return True
        else:
            _fail(
                "No quality rules seeded",
                fix="Run: python main.py seed-quality-rules  (or python main.py build-database)",
            )
            return False
    except Exception as e:
        _fail(f"Could not query quality rules ({e})")
        return False


def _check_sam_api_key():
    """Check 8: SAM.gov API key valid (uses 1 API call)."""
    import requests

    api_key = settings.SAM_API_KEY
    if not api_key:
        _fail(
            "SAM_API_KEY not configured",
            fix="Add SAM_API_KEY=your_key to .env",
        )
        return False

    url = (
        "https://api.sam.gov/opportunities/v2/search"
        f"?api_key={api_key}&limit=1"
        "&postedFrom=01/01/2026&postedTo=01/02/2026"
    )
    try:
        resp = requests.get(url, timeout=30)
        if resp.status_code == 200:
            _pass("SAM.gov API key is valid")
            return True
        else:
            _fail(
                f"SAM.gov API returned status {resp.status_code}",
                fix="Verify your SAM_API_KEY is correct and not expired",
            )
            return False
    except Exception as e:
        _fail(
            f"Could not reach SAM.gov API ({e})",
            fix="Check your internet connection",
        )
        return False


@click.command("verify-setup")
@click.option("--skip-api", is_flag=True, default=False,
              help="Skip the SAM.gov API key validation check")
def verify_setup(skip_api):
    """Verify all system prerequisites are met.

    Checks Python version, packages, .env config, MySQL binary,
    MySQL connectivity, database, schema tables, and SAM.gov API key.

    Examples:
        python main.py verify-setup
        python main.py verify-setup --skip-api
    """
    click.echo("System Prerequisite Check")
    click.echo("=========================")
    click.echo()

    total = 0
    passed = 0

    # Check 1: Python version
    total += 1
    if _check_python_version():
        passed += 1

    # Check 2: Required packages
    total += 1
    if _check_packages():
        passed += 1

    # Check 3: .env file
    total += 1
    if _check_env_file():
        passed += 1

    # Check 4: MySQL binary
    total += 1
    if _check_mysql_binary():
        passed += 1

    # Check 5: MySQL connection
    total += 1
    if _check_mysql_connection():
        passed += 1

    # Check 6: Database exists
    total += 1
    if _check_database_exists():
        passed += 1

    # Check 7: Schema tables
    total += 1
    if _check_schema_tables():
        passed += 1

    # Check 7b: Quality rules seeded
    total += 1
    if _check_quality_rules():
        passed += 1

    # Check 8: SAM.gov API key
    if skip_api:
        click.echo("[SKIP] SAM.gov API key validation (--skip-api)")
    else:
        total += 1
        if _check_sam_api_key():
            passed += 1

    failed = total - passed
    click.echo()
    click.echo(f"Results: {passed}/{total} checks passed, {failed} failed")

    sys.exit(0 if failed == 0 else 1)
