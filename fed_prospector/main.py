"""Federal Contract Prospecting System - CLI

Usage:
    python main.py build-database      Create/rebuild all database tables
    python main.py load-lookups        Load reference data from CSV files
    python main.py status              Show database status and data freshness
    python main.py check-api           Test SAM.gov API key (uses 1 API call)
    python main.py download-extract    Download SAM.gov entity extract file
    python main.py load-entities       Load entity data from extract file or API
    python main.py seed-quality-rules  Seed data quality rules into DB
    python main.py load-calc           Load GSA CALC+ labor rates (~122K unique records)
    python main.py load-opportunities  Load contract opportunities from SAM.gov API
    python main.py search              Search loaded opportunities in local DB
    python main.py add-user            Add a team member
    python main.py list-users          List team members
    python main.py create-prospect     Create a prospect from an opportunity
    python main.py update-prospect     Update prospect status
    python main.py reassign-prospect   Reassign a prospect to another user
    python main.py list-prospects      List prospects with filters
    python main.py show-prospect       Show full prospect detail
    python main.py add-note            Add a note to a prospect
    python main.py add-team-member     Add a teaming partner to a prospect
    python main.py save-search         Save a reusable search filter
    python main.py run-search          Execute a saved search
    python main.py list-searches       List saved searches
    python main.py dashboard           Show pipeline dashboard
    python main.py help                Show this help
"""

import sys
import os
from pathlib import Path

import click

# Ensure the project root is on the path so imports work
sys.path.insert(0, str(Path(__file__).parent))

from config.logging_config import setup_logging
from config import settings


@click.group()
def cli():
    """Federal Contract Prospecting System

    Gathers federal contract data from government APIs into a local MySQL
    database for WOSB/8(a) contract discovery.

    Run 'python main.py COMMAND --help' for command-specific help.
    """
    pass


@cli.command("build-database")
@click.option("--drop-first", is_flag=True, default=False,
              help="Drop and recreate all tables (DESTROYS DATA)")
def build_database(drop_first):
    """Create all database tables from SQL schema files.

    Safe to run multiple times - uses CREATE TABLE IF NOT EXISTS.
    Use --drop-first to rebuild from scratch (destroys all data).
    """
    logger = setup_logging()

    from db.connection import get_connection

    schema_dir = Path(__file__).parent / "db" / "schema"
    sql_files = sorted(schema_dir.glob("*.sql"))

    if not sql_files:
        logger.error("No SQL files found in %s", schema_dir)
        sys.exit(1)

    # Skip 00_create_database.sql (needs root privileges)
    sql_files = [f for f in sql_files if f.name != "00_create_database.sql"]

    conn = get_connection()
    cursor = conn.cursor()

    try:
        if drop_first:
            click.echo("WARNING: This will DROP ALL TABLES and destroy all data!")
            if not click.confirm("Are you sure?"):
                click.echo("Aborted.")
                return

            # Drop in reverse order to respect foreign keys
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
            cursor.execute("SELECT TABLE_NAME FROM information_schema.TABLES "
                         "WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'BASE TABLE'",
                         (settings.DB_NAME,))
            tables = [row[0] for row in cursor.fetchall()]
            for table in tables:
                cursor.execute(f"DROP TABLE IF EXISTS `{table}`")
                logger.info("Dropped table: %s", table)

            # Drop views
            cursor.execute("SELECT TABLE_NAME FROM information_schema.TABLES "
                         "WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'VIEW'",
                         (settings.DB_NAME,))
            views = [row[0] for row in cursor.fetchall()]
            for view in views:
                cursor.execute(f"DROP VIEW IF EXISTS `{view}`")
                logger.info("Dropped view: %s", view)

            cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
            conn.commit()

        for sql_file in sql_files:
            logger.info("Executing: %s", sql_file.name)
            with open(sql_file, "r", encoding="utf-8") as f:
                sql = f.read()

            # Split on semicolons and execute each statement
            for statement in sql.split(";"):
                stmt = statement.strip()
                if stmt and not stmt.startswith("--") and not stmt.startswith("USE "):
                    try:
                        cursor.execute(stmt)
                    except Exception as e:
                        logger.warning("Statement warning in %s: %s", sql_file.name, e)
            conn.commit()
            click.echo(f"  OK: {sql_file.name}")

        # Count results
        cursor.execute("SELECT COUNT(*) FROM information_schema.TABLES "
                      "WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'BASE TABLE'",
                      (settings.DB_NAME,))
        table_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM information_schema.TABLES "
                      "WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'VIEW'",
                      (settings.DB_NAME,))
        view_count = cursor.fetchone()[0]

        click.echo(f"\nDatabase ready: {table_count} tables, {view_count} views")

    except Exception as e:
        conn.rollback()
        logger.error("Database build failed: %s", e)
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()


@cli.command("load-lookups")
@click.option("--table", default="all",
              help="Load specific table (e.g., 'naics', 'psc', 'country') or 'all'")
def load_lookups(table):
    """Load reference/lookup data from CSV files into ref_* tables.

    This loads NAICS codes, PSC codes, country codes, state codes,
    FIPS counties, SBA size standards, business types, and set-aside types.

    Safe to run multiple times - truncates and reloads each table.
    """
    logger = setup_logging()
    from etl.reference_loader import ReferenceLoader

    loader = ReferenceLoader()

    if table == "all":
        click.echo("Loading all reference tables...")
        results = loader.load_all()
        click.echo("\nResults:")
        total = 0
        for tbl, count in results.items():
            status = "OK" if count >= 0 else "FAILED"
            click.echo(f"  {tbl:30s} {count:>8d}  {status}")
            if count > 0:
                total += count
        click.echo(f"  {'TOTAL':30s} {total:>8d}")

        failed = [t for t, c in results.items() if c < 0]
        if failed:
            click.echo(f"\nFailed tables: {', '.join(failed)}")
            sys.exit(1)
    else:
        # Map short names to loader methods
        method_map = {
            "naics": loader.load_naics_codes,
            "size": loader.load_size_standards,
            "footnotes": loader.load_footnotes,
            "psc": loader.load_psc_codes,
            "country": loader.load_country_codes,
            "state": loader.load_state_codes,
            "fips": loader.load_fips_counties,
            "business": loader.load_business_types,
            "setaside": loader.seed_set_aside_types,
        }
        if table not in method_map:
            click.echo(f"Unknown table: {table}")
            click.echo(f"Available: {', '.join(method_map.keys())}")
            sys.exit(1)

        count = method_map[table]()
        click.echo(f"Loaded {count} rows")


@cli.command("status")
def status():
    """Show database connection status, table row counts, and data freshness."""
    logger = setup_logging()
    from db.connection import get_connection

    click.echo("Federal Contract Prospecting System - Status\n")

    # Test connection
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT VERSION()")
        version = cursor.fetchone()[0]
        click.echo(f"MySQL: {version} ({settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME})")
        click.echo(f"User:  {settings.DB_USER}")
    except Exception as e:
        click.echo(f"ERROR: Cannot connect to MySQL: {e}")
        sys.exit(1)

    # Table counts
    click.echo("\n--- Table Row Counts ---")

    cursor.execute(
        "SELECT TABLE_NAME, TABLE_ROWS, TABLE_TYPE "
        "FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA = %s "
        "ORDER BY TABLE_TYPE, TABLE_NAME",
        (settings.DB_NAME,),
    )

    tables = cursor.fetchall()
    ref_tables = []
    data_tables = []
    etl_tables = []
    other_tables = []
    views = []

    for name, rows, ttype in tables:
        if ttype == "VIEW":
            views.append((name, rows))
        elif name.startswith("ref_"):
            ref_tables.append((name, rows))
        elif name.startswith("etl_"):
            etl_tables.append((name, rows))
        elif name in ("entity", "opportunity", "fpds_contract", "federal_organization",
                      "gsa_labor_rate", "stg_entity_raw"):
            data_tables.append((name, rows))
        else:
            other_tables.append((name, rows))

    def print_group(label, items):
        if items:
            click.echo(f"\n  {label}:")
            for name, rows in items:
                click.echo(f"    {name:35s} {rows or 0:>10,d}")

    print_group("Reference/Lookup", ref_tables)
    print_group("Data", data_tables)
    print_group("ETL/Operational", etl_tables)
    print_group("Other", other_tables)
    print_group("Views", views)

    # API rate limit status
    click.echo("\n--- API Rate Limits (Today) ---")
    cursor.execute(
        "SELECT source_system, requests_made, max_requests, last_request_at "
        "FROM etl_rate_limit WHERE request_date = CURDATE()"
    )
    limits = cursor.fetchall()
    if limits:
        for source, used, max_req, last_at in limits:
            click.echo(f"  {source}: {used}/{max_req} calls used (last: {last_at})")
    else:
        click.echo("  No API calls made today")

    # Opportunity summary
    click.echo("\n--- Opportunity Summary ---")
    try:
        cursor.execute(
            "SELECT COUNT(*) FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'opportunity'",
            (settings.DB_NAME,),
        )
        if cursor.fetchone()[0] > 0:
            cursor.execute("SELECT COUNT(*) FROM opportunity")
            opp_total = cursor.fetchone()[0]
            click.echo(f"  Total opportunities: {opp_total:,d}")

            if opp_total > 0:
                cursor.execute(
                    "SELECT COUNT(*) FROM opportunity "
                    "WHERE response_deadline > NOW() AND active = 'Y'"
                )
                opp_open = cursor.fetchone()[0]
                click.echo(f"  Open (deadline in future): {opp_open:,d}")

                cursor.execute(
                    "SELECT set_aside_code, COUNT(*) FROM opportunity "
                    "WHERE set_aside_code IS NOT NULL "
                    "GROUP BY set_aside_code ORDER BY COUNT(*) DESC LIMIT 8"
                )
                sa_rows = cursor.fetchall()
                if sa_rows:
                    click.echo("  By set-aside:")
                    for code, cnt in sa_rows:
                        click.echo(f"    {code:12s} {cnt:>8,d}")

                cursor.execute(
                    "SELECT MAX(last_loaded_at) FROM opportunity"
                )
                last_opp_load = cursor.fetchone()[0]
                if last_opp_load:
                    click.echo(f"  Last opportunity load: {last_opp_load}")
        else:
            click.echo("  opportunity table does not exist yet")
    except Exception as e:
        click.echo(f"  Could not query opportunities: {e}")

    # CALC+ labor rate freshness
    click.echo("\n--- CALC+ Labor Rate Freshness ---")
    try:
        cursor.execute(
            "SELECT started_at, status "
            "FROM etl_load_log "
            "WHERE source_system = 'GSA_CALC' AND status = 'SUCCESS' "
            "ORDER BY started_at DESC LIMIT 1"
        )
        calc_row = cursor.fetchone()
        if calc_row:
            from datetime import datetime as dt_cls2
            last_calc_load = calc_row[0]
            if hasattr(last_calc_load, 'date'):
                days_since = (dt_cls2.now() - last_calc_load).days
            else:
                days_since = None
            click.echo(f"  Last CALC+ load: {last_calc_load}")
            if days_since is not None:
                click.echo(f"  Days since last refresh: {days_since}")
                if days_since > 30:
                    click.echo(
                        f"  WARNING: CALC+ rates are {days_since} days old. "
                        f"Run 'python main.py load-calc' to refresh."
                    )
                else:
                    click.echo("  Status: Current")
        else:
            click.echo("  No CALC+ load recorded. Run 'python main.py load-calc' to load.")
    except Exception as e:
        click.echo(f"  Could not query CALC+ freshness: {e}")

    # Last loads
    click.echo("\n--- Recent Loads ---")
    cursor.execute(
        "SELECT source_system, load_type, status, started_at, "
        "records_read, records_inserted, records_updated, records_errored "
        "FROM etl_load_log ORDER BY started_at DESC LIMIT 10"
    )
    loads = cursor.fetchall()
    if loads:
        for source, ltype, stat, started, read, ins, upd, err in loads:
            click.echo(
                f"  {started} | {source:20s} | {ltype:12s} | {stat:8s} | "
                f"read={read or 0} ins={ins or 0} upd={upd or 0} err={err or 0}"
            )
    else:
        click.echo("  No loads recorded yet")

    # SAM.gov API key check
    click.echo("\n--- Configuration ---")
    if settings.SAM_API_KEY and settings.SAM_API_KEY != "your_api_key_here":
        click.echo(f"  SAM API key: configured ({settings.SAM_API_KEY[:8]}...)")
        click.echo(f"  Daily limit: {settings.SAM_DAILY_LIMIT}")
    else:
        click.echo("  SAM API key: NOT CONFIGURED")

    cursor.close()
    conn.close()


@cli.command("download-extract")
@click.option("--type", "extract_type", type=click.Choice(["monthly", "daily"]),
              default="monthly", help="Extract type: monthly (full) or daily (incremental)")
@click.option("--year", type=int, default=None,
              help="Year for monthly extract (default: current year)")
@click.option("--month", type=int, default=None,
              help="Month for monthly extract (default: current month)")
@click.option("--date", "extract_date", default=None,
              help="Date for daily extract (YYYY-MM-DD)")
def download_extract(extract_type, year, month, extract_date):
    """Download SAM.gov entity extract files.

    Monthly extracts contain ALL active entities (~500K+ records).
    Daily extracts contain only entities updated that day (Tue-Sat).

    WARNING: Each download uses 1 API call (10/day limit on free tier).

    Examples:
        python main.py download-extract --type=monthly --year=2026 --month=2
        python main.py download-extract --type=daily --date=2026-02-21
    """
    logger = setup_logging()
    from datetime import date as date_cls, datetime as dt_cls
    from api_clients.sam_extract_client import SAMExtractClient

    if not settings.SAM_API_KEY or settings.SAM_API_KEY == "your_api_key_here":
        click.echo("ERROR: SAM_API_KEY not configured in .env file")
        sys.exit(1)

    client = SAMExtractClient()

    if extract_type == "monthly":
        today = date_cls.today()
        year = year or today.year
        month = month or today.month
        click.echo(f"Downloading monthly extract for {year}-{month:02d}...")
        click.echo(f"API calls remaining: {client._get_remaining_requests()}")
        try:
            paths = client.download_monthly_extract(year, month)
            click.echo(f"\nExtracted files:")
            for p in paths:
                click.echo(f"  {p}")
            click.echo("\nUse 'python main.py load-entities --file=<path>' to load.")
        except Exception as e:
            click.echo(f"ERROR: {e}")
            sys.exit(1)

    elif extract_type == "daily":
        if not extract_date:
            extract_date = date_cls.today().isoformat()
        try:
            d = date_cls.fromisoformat(extract_date)
        except ValueError:
            click.echo(f"ERROR: Invalid date format: {extract_date} (use YYYY-MM-DD)")
            sys.exit(1)

        click.echo(f"Downloading daily extract for {d}...")
        click.echo(f"API calls remaining: {client._get_remaining_requests()}")
        try:
            paths = client.download_daily_extract(d)
            click.echo(f"\nExtracted files:")
            for p in paths:
                click.echo(f"  {p}")
            click.echo("\nUse 'python main.py load-entities --file=<path>' to load.")
        except Exception as e:
            click.echo(f"ERROR: {e}")
            sys.exit(1)


@cli.command("load-entities")
@click.option("--mode", type=click.Choice(["full", "daily"]), default="full",
              help="Load mode: full (monthly extract) or daily (incremental)")
@click.option("--file", "file_path", default=None,
              help="Path to extract file to load (.dat or .json)")
@click.option("--date", "load_date", default=None,
              help="For daily mode: date of extract (YYYY-MM-DD)")
@click.option("--batch-size", default=1000, type=int,
              help="Records per batch commit for JSON mode (default: 1000)")
def load_entities(mode, file_path, load_date, batch_size):
    """Load SAM.gov entity data into the database.

    Automatically detects file format:
      .dat  -> Bulk load via LOAD DATA INFILE (fast, for monthly extracts)
      .json -> Streaming load with change detection (for JSON extracts/daily)

    Examples:
        python main.py load-entities --mode=full --file=data/downloads/SAM_PUBLIC_MONTHLY_V2_20260201.dat
        python main.py load-entities --mode=daily --file=data/downloads/daily.json
    """
    logger = setup_logging()

    if not file_path:
        click.echo("ERROR: --file is required. Download an extract first:")
        click.echo("  python main.py download-extract --type=monthly")
        sys.exit(1)

    from pathlib import Path as P
    fp = P(file_path)
    if not fp.exists():
        click.echo(f"ERROR: File not found: {file_path}")
        sys.exit(1)

    file_ext = fp.suffix.lower()

    if file_ext == ".dat":
        # ---- DAT file: use bulk loader (LOAD DATA INFILE) ----
        from etl.dat_parser import parse_dat_file, get_dat_record_count
        from etl.bulk_loader import BulkLoader

        try:
            record_count = get_dat_record_count(str(fp))
            click.echo(f"Loading DAT file: {fp.name}")
            click.echo(f"  Records in file (from header): {record_count:,d}")
            click.echo(f"  Method: LOAD DATA INFILE (bulk)")
            click.echo(f"  Mode: {mode}")
        except ValueError as e:
            click.echo(f"WARNING: Could not read DAT header: {e}")
            click.echo(f"Loading DAT file: {fp.name}")

        loader = BulkLoader()
        try:
            entity_iter = parse_dat_file(str(fp))
            stats = loader.bulk_load_entities(
                entity_iter,
                source_file=str(fp),
                load_type="FULL" if mode == "full" else "INCREMENTAL",
            )
            click.echo(f"\nBulk load complete!")
            click.echo(f"  Entities loaded:   {stats.get('records_inserted', 0):>10,d}")
            child_counts = stats.get("child_counts", {})
            if child_counts:
                click.echo(f"\n  Child table rows:")
                for table, count in child_counts.items():
                    if count > 0:
                        click.echo(f"    {table:35s} {count:>10,d}")
        except Exception as e:
            logger.exception("DAT bulk load failed")
            click.echo(f"\nERROR: {e}")
            sys.exit(1)

    else:
        # ---- JSON file: use streaming loader with change detection ----
        from etl.entity_loader import EntityLoader
        from etl.change_detector import ChangeDetector
        from etl.data_cleaner import DataCleaner
        from etl.load_manager import LoadManager

        click.echo(f"Loading JSON file: {fp.name}")
        click.echo(f"  Mode: {mode} | Batch size: {batch_size}")

        loader = EntityLoader(
            change_detector=ChangeDetector(),
            data_cleaner=DataCleaner(),
            load_manager=LoadManager(),
        )
        loader.BATCH_SIZE = batch_size

        try:
            stats = loader.load_from_json_extract(str(fp), mode=mode)
            click.echo(f"\nLoad complete!")
            click.echo(f"  Records read:      {stats.get('records_read', 0):>10,d}")
            click.echo(f"  Records inserted:  {stats.get('records_inserted', 0):>10,d}")
            click.echo(f"  Records updated:   {stats.get('records_updated', 0):>10,d}")
            click.echo(f"  Records unchanged: {stats.get('records_unchanged', 0):>10,d}")
            click.echo(f"  Records errored:   {stats.get('records_errored', 0):>10,d}")
            clean_stats = stats.get("cleaning_stats", {})
            if clean_stats:
                click.echo(f"\n  Data cleaning applied:")
                for rule, count in clean_stats.items():
                    if count > 0:
                        click.echo(f"    {rule:30s} {count:>8,d}")
        except Exception as e:
            logger.exception("Entity load failed")
            click.echo(f"\nERROR: {e}")
            sys.exit(1)


@cli.command("seed-quality-rules")
def seed_quality_rules():
    """Seed the etl_data_quality_rule table with initial data quality rules.

    These rules define how the data cleaner handles known SAM.gov data
    quality issues during entity loading.

    Safe to run multiple times - truncates and reloads.
    """
    logger = setup_logging()
    from db.connection import get_connection

    rules = [
        ("clean_zip_city_state", "Remove city/state/country contamination from ZIP fields",
         "entity_address", "zip_code", "CLEAN", '{"pattern": "city_state_in_zip"}'),
        ("clean_zip_po_box", "Remove PO BOX data from ZIP fields",
         "entity_address", "zip_code", "CLEAN", '{"pattern": "po_box_in_zip"}'),
        ("clean_state_date", "Remove date values from state fields",
         "entity_address", "state_or_province", "CLEAN", '{"pattern": "date_in_state"}'),
        ("flag_foreign_province", "Flag non-US addresses with province names > 2 chars",
         "entity_address", "state_or_province", "VALIDATE", '{"max_length_us": 2}'),
        ("normalize_country_chars", "Normalize non-ASCII characters in country names",
         "ref_country_code", "country_name", "TRANSFORM", '{"normalize": "nfkd"}'),
        ("map_special_countries", "Handle XKS/XWB/XGZ country codes",
         "entity_address", "country_code", "TRANSFORM", '{"codes": ["XKS","XWB","XGZ"]}'),
        ("split_cage_codes", "Split comma-separated CAGE codes, keep first",
         "entity", "cage_code", "CLEAN", '{"separator": ", "}'),
        ("flag_retired_naics", "Flag NAICS codes not in current lookup table",
         "entity_naics", "naics_code", "VALIDATE", '{"check_ref_table": true}'),
        ("fix_pipe_escapes", "Fix escaped pipe characters in DAT file lines",
         None, None, "CLEAN", '{"source_format": "dat"}'),
        ("normalize_dates", "Convert YYYYMMDD and other formats to DATE type",
         "entity", None, "TRANSFORM", '{"formats": ["YYYYMMDD","YYYY-MM-DD","MM/dd/yyyy"]}'),
    ]

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("TRUNCATE TABLE etl_data_quality_rule")
        sql = (
            "INSERT INTO etl_data_quality_rule "
            "(rule_name, description, target_table, target_column, rule_type, rule_definition, is_active, priority) "
            "VALUES (%s, %s, %s, %s, %s, %s, 'Y', %s)"
        )
        rows = [(name, desc, table, col, rtype, rdef, (i + 1) * 10)
                for i, (name, desc, table, col, rtype, rdef) in enumerate(rules)]
        cursor.executemany(sql, rows)
        conn.commit()
        click.echo(f"Seeded {len(rules)} data quality rules into etl_data_quality_rule")
    except Exception as e:
        conn.rollback()
        click.echo(f"ERROR: {e}")
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()


@cli.command("load-calc")
def load_calc():
    """Load GSA CALC+ labor rates into gsa_labor_rate table. No API key needed.

    Fetches the full CALC+ ceiling rates dataset via the v3 API, truncates
    the gsa_labor_rate table, and reloads all records. The API is
    Elasticsearch-backed with a 10K result window, so multiple queries with
    different sort orderings are used to maximize coverage (~122K unique
    rates out of ~230K total).

    No authentication or API key is required. No rate limits.

    Example:
        python main.py load-calc
    """
    import time
    logger = setup_logging()

    from api_clients.calc_client import CalcPlusClient
    from etl.calc_loader import CalcLoader

    client = CalcPlusClient()
    loader = CalcLoader()

    click.echo("GSA CALC+ Labor Rate Load")
    click.echo("  Data source: GSA CALC+ API (refreshed nightly by GSA)")
    click.echo("  Rates loaded: current fiscal year ceiling rates from GSA schedule contracts")
    click.echo("  Method: API multi-sort de-duplication")
    click.echo("  Target: gsa_labor_rate (truncate + reload)")
    click.echo("")
    click.echo("  NOTE: These are GSA schedule CEILING rates, not SCA wage")
    click.echo("        determinations. For SCA minimums, see DOL wage determinations.")
    click.echo("")

    t_start = time.time()

    def progress(seen_count, label):
        click.echo("  [%s] %d unique rates so far" % (label, seen_count))

    try:
        stats = loader.full_refresh(client, progress_callback=progress)
        elapsed = time.time() - t_start

        click.echo("")
        click.echo("Load complete!")
        click.echo("  Records fetched:   %10d" % stats["records_read"])
        click.echo("  Records inserted:  %10d" % stats["records_inserted"])
        click.echo("  Records errored:   %10d" % stats["records_errored"])
        click.echo("  Time:              %10.1f seconds" % elapsed)

        # Show contract date range of loaded data
        try:
            from db.connection import get_connection as gc
            conn = gc()
            cur = conn.cursor()
            cur.execute(
                "SELECT MIN(contract_start), MAX(contract_end) "
                "FROM gsa_labor_rate"
            )
            row = cur.fetchone()
            if row and row[0] and row[1]:
                click.echo("")
                click.echo("  Contract date range: %s to %s" % (row[0], row[1]))
            cur.close()
            conn.close()
        except Exception:
            pass  # Non-critical, don't fail the load

    except Exception as e:
        elapsed = time.time() - t_start
        logger.exception("CALC+ load failed")
        click.echo("\nERROR after %.1f seconds: %s" % (elapsed, e))
        sys.exit(1)


@cli.command("check-api")
def check_api():
    """Test the SAM.gov API key with a minimal request.

    WARNING: This uses 1 of your daily API calls.
    """
    logger = setup_logging()

    if not settings.SAM_API_KEY or settings.SAM_API_KEY == "your_api_key_here":
        click.echo("ERROR: SAM_API_KEY not configured in .env file")
        sys.exit(1)

    click.echo(f"Testing SAM.gov API key ({settings.SAM_API_KEY[:8]}...)...")
    click.echo(f"Daily limit: {settings.SAM_DAILY_LIMIT}")
    click.echo("WARNING: This will use 1 API call.\n")

    import requests as req

    try:
        resp = req.get(
            "https://api.sam.gov/opportunities/v2/search",
            params={
                "api_key": settings.SAM_API_KEY,
                "postedFrom": "01/01/2025",
                "postedTo": "01/31/2025",
                "limit": 1,
            },
            timeout=30,
        )
        click.echo(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            total = data.get("totalRecords", "unknown")
            click.echo(f"Total opportunities in test query: {total}")
            click.echo("API key is WORKING!")
        elif resp.status_code == 403:
            click.echo("API key is EXPIRED or INVALID. Regenerate at sam.gov.")
            sys.exit(1)
        elif resp.status_code == 429:
            click.echo("Rate limited. Daily limit already reached.")
        else:
            click.echo(f"Unexpected response: {resp.text[:300]}")
    except Exception as e:
        click.echo(f"Connection error: {e}")
        sys.exit(1)


@cli.command("load-opportunities")
@click.option("--days-back", default=7, type=int,
              help="Load opportunities posted in the last N days (default: 7)")
@click.option("--set-aside", "set_aside", default=None,
              help="Filter by set-aside code (e.g., WOSB, 8A, SBA). "
                   "If not specified, loads priority set-asides within call budget.")
@click.option("--naics", default=None,
              help="Filter by NAICS code")
@click.option("--posted-from", "posted_from", default=None,
              help="Start date (MM/dd/yyyy) - overrides --days-back")
@click.option("--posted-to", "posted_to", default=None,
              help="End date (MM/dd/yyyy) - defaults to today")
@click.option("--historical", is_flag=True, default=False,
              help="Load 2 years of historical data (breaks into 1-year chunks)")
@click.option("--max-calls", default=5, type=int,
              help="Max API calls for this invocation (default: 5, reserves 5 of 10/day for other work)")
def load_opportunities(days_back, set_aside, naics, posted_from, posted_to, historical, max_calls):
    """Load contract opportunities from the SAM.gov Opportunities API.

    Fetches opportunities matching the given filters and loads them into
    the local database with change detection and history tracking.

    By default, reserves only 5 API calls for opportunity loading (out of
    10/day free-tier limit), saving the other 5 for entity/other work.
    Use --max-calls to adjust.

    When no --set-aside is specified, loads the top 4 priority set-asides
    (WOSB, EDWOSB, 8A, 8AN) which fit within the 5-call budget for date
    ranges up to 1 year.

    WARNING: Each API call uses 1 of your daily API calls. Multiple
    set-aside types and date chunks each require separate API calls.

    Examples:
        python main.py load-opportunities
        python main.py load-opportunities --days-back=30
        python main.py load-opportunities --set-aside=WOSB --naics=541511
        python main.py load-opportunities --posted-from=01/01/2026 --posted-to=02/01/2026
        python main.py load-opportunities --historical
        python main.py load-opportunities --max-calls=8
    """
    logger = setup_logging()
    from datetime import date as date_cls, timedelta
    from api_clients.sam_opportunity_client import (
        SAMOpportunityClient, ALL_SB_SET_ASIDES, PRIORITY_SET_ASIDES,
    )
    from etl.opportunity_loader import OpportunityLoader
    from etl.load_manager import LoadManager

    if not settings.SAM_API_KEY or settings.SAM_API_KEY == "your_api_key_here":
        click.echo("ERROR: SAM_API_KEY not configured in .env file")
        sys.exit(1)

    client = SAMOpportunityClient(call_budget=max_calls)
    loader = OpportunityLoader()
    load_manager = LoadManager()

    # --- Determine date range ---
    today = date_cls.today()

    if historical:
        dt_from = today - timedelta(days=730)  # ~2 years
        dt_to = today
        load_type = "HISTORICAL"
    elif posted_from:
        # posted_from is already in MM/dd/yyyy format for the API
        dt_from = posted_from
        dt_to = posted_to or today.strftime("%m/%d/%Y")
        load_type = "INCREMENTAL"
    else:
        dt_from = today - timedelta(days=days_back)
        dt_to = today
        load_type = "INCREMENTAL"

    # --- Determine which set-aside codes to query ---
    if set_aside:
        # User specified a single set-aside type
        query_codes = [set_aside]
        set_aside_label = set_aside
    else:
        # Default: use priority set-asides (WOSB, EDWOSB, 8A, 8AN) which
        # fit within the 5-call budget for date ranges up to 1 year.
        # With a larger budget, use all 12 set-aside types.
        query_codes = PRIORITY_SET_ASIDES if max_calls <= 5 else ALL_SB_SET_ASIDES
        set_aside_label = f"top {len(query_codes)} priority" if query_codes is PRIORITY_SET_ASIDES else f"all {len(query_codes)} SB"

    # --- Estimate API calls and warn user ---
    remaining = client._get_remaining_requests()
    est_calls = client.estimate_calls_needed(query_codes, dt_from, dt_to)

    click.echo("SAM.gov Opportunities Load")
    click.echo(f"  Date range:  {client._format_date(dt_from)} to {client._format_date(dt_to)}")
    click.echo(f"  Set-asides:  {set_aside_label} ({', '.join(query_codes)})")
    if naics:
        click.echo(f"  NAICS:       {naics}")
    click.echo(f"  Load type:   {load_type}")
    click.echo(f"  Call budget: {max_calls}")
    click.echo(f"  Est. API calls: ~{est_calls} (at minimum, more with pagination)")
    click.echo(f"  API calls remaining today: {remaining}")

    if est_calls > max_calls:
        click.echo(
            f"\nWARNING: Estimated calls ({est_calls}) exceed call budget "
            f"({max_calls}). Some set-aside types will be skipped."
        )

    if est_calls > remaining:
        click.echo(
            f"\nWARNING: Estimated calls ({est_calls}) may exceed remaining "
            f"daily quota ({remaining}). Some set-aside types may not be queried."
        )

    if historical:
        click.echo(
            "\nHistorical load will fetch 2 years of data across "
            f"{len(query_codes)} set-aside types."
        )
        if est_calls > max_calls:
            click.echo(
                f"NOTE: Budget is tight ({max_calls} calls for {est_calls} "
                f"estimated). Consider using --set-aside to focus on one type, "
                f"or --max-calls to increase the budget."
            )
        if not click.confirm("Proceed?"):
            click.echo("Aborted.")
            return

    # --- Create load log entry ---
    params_dict = {
        "days_back": days_back,
        "set_aside": set_aside,
        "set_aside_codes": query_codes,
        "naics": naics,
        "posted_from": client._format_date(dt_from),
        "posted_to": client._format_date(dt_to),
        "historical": historical,
        "max_calls": max_calls,
    }
    load_id = load_manager.start_load(
        source_system="SAM_OPPORTUNITY",
        load_type=load_type,
        parameters=params_dict,
    )
    click.echo(f"\nLoad started (load_id={load_id})")

    # --- Fetch opportunities ---
    try:
        if set_aside:
            # Single set-aside search (not subject to budget)
            click.echo(f"Searching for set-aside: {set_aside}...")
            results = list(client.search_opportunities(
                posted_from=dt_from,
                posted_to=dt_to,
                set_aside=set_aside,
                naics=naics,
            ))
        else:
            # Multiple set-aside types (respects call budget)
            click.echo(f"Searching {len(query_codes)} set-aside types within {max_calls}-call budget...")
            results = client.load_all_set_asides(
                posted_from=dt_from,
                posted_to=dt_to,
                naics=naics,
                set_aside_codes=query_codes,
            )

        click.echo(f"Retrieved {len(results):,d} unique opportunities from API")

        if not results:
            click.echo("No opportunities found matching the criteria.")
            load_manager.complete_load(load_id, records_read=0)
            return

        # --- Load into database ---
        click.echo("Loading into database...")
        stats = loader.load_opportunities(results, load_id)

        # --- Complete load log ---
        load_manager.complete_load(
            load_id,
            records_read=stats["records_read"],
            records_inserted=stats["records_inserted"],
            records_updated=stats["records_updated"],
            records_unchanged=stats["records_unchanged"],
            records_errored=stats["records_errored"],
        )

        click.echo(f"\nLoad complete!")
        click.echo(f"  Records read:      {stats['records_read']:>10,d}")
        click.echo(f"  Records inserted:  {stats['records_inserted']:>10,d}")
        click.echo(f"  Records updated:   {stats['records_updated']:>10,d}")
        click.echo(f"  Records unchanged: {stats['records_unchanged']:>10,d}")
        click.echo(f"  Records errored:   {stats['records_errored']:>10,d}")

    except Exception as e:
        load_manager.fail_load(load_id, str(e))
        logger.exception("Opportunity load failed")
        click.echo(f"\nERROR: {e}")
        sys.exit(1)


@cli.command("search")
@click.option("--set-aside", "set_aside", default=None,
              help="Filter by set-aside code (WOSB, 8A, etc.)")
@click.option("--naics", default=None,
              help="Filter by NAICS code")
@click.option("--open-only", is_flag=True, default=False,
              help="Only show opportunities with future response deadlines")
@click.option("--days", default=30, type=int,
              help="Show opportunities posted in last N days (default: 30)")
@click.option("--limit", default=25, type=int,
              help="Max results to show (default: 25)")
def search(set_aside, naics, open_only, days, limit):
    """Search loaded opportunities in the local database.

    Queries the opportunity table (no API calls). Results are ordered by
    response deadline (most urgent first).

    Examples:
        python main.py search
        python main.py search --set-aside=WOSB --open-only
        python main.py search --naics=541511 --days=60
        python main.py search --set-aside=8A --limit=50
    """
    logger = setup_logging()
    from datetime import datetime as dt_cls, timedelta
    from db.connection import get_connection

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Build query dynamically
        where_clauses = []
        params = []

        # Date filter: posted in last N days
        cutoff = (dt_cls.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        where_clauses.append("o.posted_date >= %s")
        params.append(cutoff)

        if set_aside:
            where_clauses.append("o.set_aside_code = %s")
            params.append(set_aside)

        if naics:
            where_clauses.append("o.naics_code = %s")
            params.append(naics)

        if open_only:
            where_clauses.append("o.response_deadline > NOW()")
            where_clauses.append("o.active = 'Y'")

        where_sql = " AND ".join(where_clauses)

        sql = (
            "SELECT o.title, o.set_aside_code, o.naics_code, "
            "  o.response_deadline, o.posted_date, o.department_name, "
            "  n.description "
            "FROM opportunity o "
            "LEFT JOIN ref_naics_code n ON o.naics_code = n.naics_code "
            f"WHERE {where_sql} "
            "ORDER BY o.response_deadline ASC "
            "LIMIT %s"
        )
        params.append(limit)

        cursor.execute(sql, params)
        rows = cursor.fetchall()

        if not rows:
            click.echo("No opportunities found matching the criteria.")
            click.echo(f"  Filters: set-aside={set_aside or 'any'}, "
                       f"naics={naics or 'any'}, "
                       f"posted in last {days} days"
                       + (", open only" if open_only else ""))
            return

        # Print header
        click.echo(f"\nFound {len(rows)} opportunities"
                   + (f" (showing top {limit})" if len(rows) == limit else ""))
        click.echo("")

        # Column headers
        header = (
            f"{'Title':<60s}  {'Set-Aside':>9s}  {'NAICS':>6s}  "
            f"{'Deadline':>12s}  {'Days Left':>9s}  {'Posted':>10s}  "
            f"{'Department':<30s}"
        )
        click.echo(header)
        click.echo("-" * len(header))

        now = dt_cls.now()
        for title, sa_code, naics_code, deadline, posted, dept, naics_desc in rows:
            # Truncate title
            title_str = (title[:57] + "...") if title and len(title) > 60 else (title or "")
            title_str = f"{title_str:<60s}"

            sa_str = f"{(sa_code or ''):>9s}"
            naics_str = f"{(naics_code or ''):>6s}"

            # Response deadline
            if deadline:
                deadline_str = deadline.strftime("%Y-%m-%d")
                delta = deadline - now
                days_left = delta.days
                if days_left < 0:
                    days_str = "CLOSED"
                else:
                    days_str = str(days_left)
            else:
                deadline_str = "N/A"
                days_str = "N/A"

            deadline_str = f"{deadline_str:>12s}"
            days_str = f"{days_str:>9s}"

            # Posted date
            if posted:
                posted_str = posted.strftime("%Y-%m-%d")
            else:
                posted_str = "N/A"
            posted_str = f"{posted_str:>10s}"

            # Department (truncated)
            dept_str = (dept[:27] + "...") if dept and len(dept) > 30 else (dept or "")
            dept_str = f"{dept_str:<30s}"

            click.echo(
                f"{title_str}  {sa_str}  {naics_str}  "
                f"{deadline_str}  {days_str}  {posted_str}  "
                f"{dept_str}"
            )

        # Summary footer
        click.echo("")
        click.echo(f"Filters: set-aside={set_aside or 'any'}, "
                   f"naics={naics or 'any'}, "
                   f"posted in last {days} days"
                   + (", open only" if open_only else ""))

    except Exception as e:
        logger.exception("Search failed")
        click.echo(f"ERROR: {e}")
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()


# ===================================================================
# Phase 4: Prospecting Pipeline Commands
# ===================================================================

@cli.command("add-user")
@click.option("--username", required=True, help="Unique short username")
@click.option("--name", "display_name", required=True, help="Full display name")
@click.option("--email", default=None, help="Email address")
@click.option("--role", default="MEMBER", help="User role (default: MEMBER)")
def add_user(username, display_name, email, role):
    """Add a team member to the system.

    Examples:
        python main.py add-user --username jdoe --name "Jane Doe" --email jane@example.com
        python main.py add-user --username admin1 --name "Admin" --role ADMIN
    """
    setup_logging()
    from etl.prospect_manager import ProspectManager

    mgr = ProspectManager()
    try:
        user_id = mgr.add_user(username, display_name, email=email, role=role)
        click.echo(f"Created user '{username}' (user_id={user_id})")
    except ValueError as e:
        click.echo(f"ERROR: {e}")
        sys.exit(1)
    except Exception as e:
        click.echo(f"ERROR: {e}")
        sys.exit(1)


@cli.command("list-users")
@click.option("--all", "show_all", is_flag=True, default=False,
              help="Include inactive users")
def list_users(show_all):
    """List team members.

    By default shows only active users. Use --all to include inactive.
    """
    setup_logging()
    from etl.prospect_manager import ProspectManager

    mgr = ProspectManager()
    users = mgr.list_users(active_only=not show_all)

    if not users:
        click.echo("No users found.")
        return

    click.echo(f"\n{'ID':>4s}  {'Username':<15s}  {'Display Name':<25s}  {'Email':<30s}  {'Role':<10s}  {'Active':>6s}")
    click.echo("-" * 100)
    for u in users:
        click.echo(
            f"{u['user_id']:>4d}  {u['username']:<15s}  {u['display_name']:<25s}  "
            f"{(u['email'] or ''):<30s}  {(u['role'] or ''):<10s}  {u['is_active']:>6s}"
        )
    click.echo(f"\nTotal: {len(users)} user(s)")


@cli.command("create-prospect")
@click.option("--notice-id", required=True, help="Opportunity notice_id")
@click.option("--assign-to", required=True, help="Username to assign to")
@click.option("--priority", default="MEDIUM",
              type=click.Choice(["LOW", "MEDIUM", "HIGH", "CRITICAL"], case_sensitive=False),
              help="Priority level (default: MEDIUM)")
@click.option("--notes", default=None, help="Optional creation notes")
def create_prospect(notice_id, assign_to, priority, notes):
    """Create a new prospect from an opportunity in the database.

    Validates that the notice_id exists in the opportunity table and that
    the assigned user exists and is active.

    Examples:
        python main.py create-prospect --notice-id ABC123 --assign-to jdoe --priority HIGH
        python main.py create-prospect --notice-id XYZ789 --assign-to jsmith
    """
    setup_logging()
    from etl.prospect_manager import ProspectManager

    mgr = ProspectManager()
    try:
        prospect_id = mgr.create_prospect(
            notice_id, assign_to, priority=priority.upper(), notes=notes
        )
        click.echo(f"Created prospect {prospect_id} for notice_id='{notice_id}' assigned to '{assign_to}'")
    except ValueError as e:
        click.echo(f"ERROR: {e}")
        sys.exit(1)
    except Exception as e:
        click.echo(f"ERROR: {e}")
        sys.exit(1)


@cli.command("update-prospect")
@click.option("--id", "prospect_id", required=True, type=int, help="Prospect ID")
@click.option("--status", required=True,
              type=click.Choice(
                  ["REVIEWING", "PURSUING", "BID_SUBMITTED", "WON", "LOST", "DECLINED", "NO_BID"],
                  case_sensitive=False,
              ),
              help="New status")
@click.option("--user", "username", required=True, help="Username performing the update")
@click.option("--notes", default=None, help="Optional notes about this status change")
def update_prospect(prospect_id, status, username, notes):
    """Update the status of a prospect.

    Status transitions must follow the defined flow:
      NEW -> REVIEWING -> PURSUING -> BID_SUBMITTED -> WON/LOST
      NEW/REVIEWING -> DECLINED/NO_BID

    Examples:
        python main.py update-prospect --id 1 --status REVIEWING --user jdoe --notes "Looks promising"
        python main.py update-prospect --id 1 --status DECLINED --user jdoe --notes "Outside our NAICS"
    """
    setup_logging()
    from etl.prospect_manager import ProspectManager

    mgr = ProspectManager()
    try:
        mgr.update_status(prospect_id, status.upper(), username, notes=notes)
        click.echo(f"Prospect {prospect_id} status updated to {status.upper()}")
    except ValueError as e:
        click.echo(f"ERROR: {e}")
        sys.exit(1)
    except Exception as e:
        click.echo(f"ERROR: {e}")
        sys.exit(1)


@cli.command("reassign-prospect")
@click.option("--id", "prospect_id", required=True, type=int, help="Prospect ID")
@click.option("--to", "new_username", required=True, help="New assignee username")
@click.option("--by", "by_username", required=True, help="Username performing the reassignment")
@click.option("--notes", default=None, help="Optional notes")
def reassign_prospect(prospect_id, new_username, by_username, notes):
    """Reassign a prospect to a different team member.

    Examples:
        python main.py reassign-prospect --id 1 --to jsmith --by jdoe
        python main.py reassign-prospect --id 1 --to jsmith --by jdoe --notes "Jsmith has domain expertise"
    """
    setup_logging()
    from etl.prospect_manager import ProspectManager

    mgr = ProspectManager()
    try:
        mgr.reassign_prospect(prospect_id, new_username, by_username, notes=notes)
        click.echo(f"Prospect {prospect_id} reassigned to '{new_username}'")
    except ValueError as e:
        click.echo(f"ERROR: {e}")
        sys.exit(1)
    except Exception as e:
        click.echo(f"ERROR: {e}")
        sys.exit(1)


@cli.command("list-prospects")
@click.option("--status", default=None, help="Filter by status")
@click.option("--assigned-to", default=None, help="Filter by assigned username")
@click.option("--priority", default=None,
              type=click.Choice(["LOW", "MEDIUM", "HIGH", "CRITICAL"], case_sensitive=False),
              help="Filter by priority")
@click.option("--open-only", is_flag=True, default=False,
              help="Exclude terminal statuses (WON, LOST, DECLINED, NO_BID)")
def list_prospects(status, assigned_to, priority, open_only):
    """List prospects with optional filters.

    Joins to opportunity table for title, deadline, and set-aside info.
    Results are sorted by response deadline (most urgent first).

    Examples:
        python main.py list-prospects
        python main.py list-prospects --status REVIEWING
        python main.py list-prospects --assigned-to jdoe --open-only
        python main.py list-prospects --priority HIGH
    """
    setup_logging()
    from etl.prospect_manager import ProspectManager

    mgr = ProspectManager()
    prospects = mgr.list_prospects(
        status=status.upper() if status else None,
        assigned_to=assigned_to,
        priority=priority.upper() if priority else None,
        open_only=open_only,
    )

    if not prospects:
        click.echo("No prospects found matching the criteria.")
        return

    click.echo(f"\n{'ID':>4s}  {'Status':<15s}  {'Pri':<8s}  {'Title':<45s}  "
               f"{'Set-Aside':>9s}  {'Deadline':>12s}  {'Days':>5s}  {'Assigned To':<15s}")
    click.echo("-" * 130)

    from datetime import datetime as dt_cls
    now = dt_cls.now()
    for p in prospects:
        title = p.get("title") or ""
        title_str = (title[:42] + "...") if len(title) > 45 else title

        deadline = p.get("response_deadline")
        if deadline:
            if isinstance(deadline, str):
                deadline = dt_cls.strptime(deadline, "%Y-%m-%d %H:%M:%S")
            deadline_str = deadline.strftime("%Y-%m-%d")
            days_left = (deadline - now).days
            days_str = str(days_left) if days_left >= 0 else "PAST"
        else:
            deadline_str = "N/A"
            days_str = "N/A"

        click.echo(
            f"{p['prospect_id']:>4d}  {p['status']:<15s}  {p['priority']:<8s}  "
            f"{title_str:<45s}  {(p.get('set_aside_code') or ''):>9s}  "
            f"{deadline_str:>12s}  {days_str:>5s}  {(p.get('assigned_to') or ''):<15s}"
        )

    click.echo(f"\nTotal: {len(prospects)} prospect(s)")


@cli.command("show-prospect")
@click.option("--id", "prospect_id", required=True, type=int, help="Prospect ID")
def show_prospect(prospect_id):
    """Show full prospect detail including opportunity info, notes, and team members.

    Examples:
        python main.py show-prospect --id 1
    """
    setup_logging()
    from etl.prospect_manager import ProspectManager

    mgr = ProspectManager()
    detail = mgr.get_prospect_detail(prospect_id)

    if not detail:
        click.echo(f"Prospect {prospect_id} not found.")
        sys.exit(1)

    p = detail["prospect"]

    click.echo(f"\n{'='*70}")
    click.echo(f"  PROSPECT #{p['prospect_id']}")
    click.echo(f"{'='*70}")
    click.echo(f"  Status:      {p['status']}")
    click.echo(f"  Priority:    {p['priority']}")
    click.echo(f"  Assigned to: {p.get('assigned_to_username', 'N/A')} ({p.get('assigned_name', '')})")
    if p.get('go_no_go_score') is not None:
        click.echo(f"  Go/No-Go:    {p['go_no_go_score']}/40")
    if p.get('win_probability') is not None:
        click.echo(f"  Win Prob:    {p['win_probability']}%")
    if p.get('estimated_value') is not None:
        click.echo(f"  Est. Value:  ${p['estimated_value']:,.2f}")
    click.echo(f"  Created:     {p['created_at']}")
    click.echo(f"  Updated:     {p['updated_at']}")

    click.echo(f"\n  --- Opportunity ---")
    click.echo(f"  Title:       {p.get('title', 'N/A')}")
    click.echo(f"  Notice ID:   {p['notice_id']}")
    if p.get('solicitation_number'):
        click.echo(f"  Sol #:       {p['solicitation_number']}")
    click.echo(f"  Department:  {p.get('department_name', 'N/A')}")
    if p.get('sub_tier'):
        click.echo(f"  Sub-tier:    {p['sub_tier']}")
    if p.get('office'):
        click.echo(f"  Office:      {p['office']}")
    click.echo(f"  Set-aside:   {p.get('set_aside_code', 'N/A')} ({p.get('set_aside_description', '')})")
    click.echo(f"  NAICS:       {p.get('naics_code', 'N/A')}")
    click.echo(f"  Posted:      {p.get('posted_date', 'N/A')}")
    click.echo(f"  Deadline:    {p.get('response_deadline', 'N/A')}")
    if p.get('pop_state') or p.get('pop_city'):
        click.echo(f"  POP:         {p.get('pop_city', '')}, {p.get('pop_state', '')} {p.get('pop_zip', '')}")
    if p.get('link'):
        click.echo(f"  Link:        {p['link']}")
    if p.get('award_amount') is not None:
        click.echo(f"  Award Amt:   ${p['award_amount']:,.2f}")

    # Outcome info
    if p.get('outcome'):
        click.echo(f"\n  --- Outcome ---")
        click.echo(f"  Outcome:     {p['outcome']}")
        if p.get('outcome_date'):
            click.echo(f"  Date:        {p['outcome_date']}")
        if p.get('outcome_notes'):
            click.echo(f"  Notes:       {p['outcome_notes']}")

    # Team members
    team = detail.get("team_members", [])
    if team:
        click.echo(f"\n  --- Team Members ({len(team)}) ---")
        for tm in team:
            name = tm.get("legal_business_name") or "(not in DB)"
            click.echo(f"    {tm['role']:<12s}  {tm['uei_sam']}  {name}")
            if tm.get("notes"):
                click.echo(f"               {tm['notes']}")

    # Notes
    notes = detail.get("notes", [])
    if notes:
        click.echo(f"\n  --- Activity Log ({len(notes)} notes) ---")
        for n in notes:
            ts = n["created_at"]
            if hasattr(ts, "strftime"):
                ts = ts.strftime("%Y-%m-%d %H:%M")
            click.echo(f"    [{ts}] {n.get('username', '?')} ({n['note_type']}): {n['note_text']}")
    else:
        click.echo(f"\n  --- Activity Log (0 notes) ---")

    click.echo("")


@cli.command("add-note")
@click.option("--prospect-id", required=True, type=int, help="Prospect ID")
@click.option("--user", required=True, help="Username adding the note")
@click.option("--type", "note_type", required=True,
              type=click.Choice(
                  ["COMMENT", "STATUS_CHANGE", "ASSIGNMENT", "DECISION", "REVIEW", "MEETING"],
                  case_sensitive=False,
              ),
              help="Note type")
@click.option("--text", required=True, help="Note text content")
def add_note(prospect_id, user, note_type, text):
    """Add a note to a prospect.

    Examples:
        python main.py add-note --prospect-id 1 --user jdoe --type COMMENT --text "Spoke with CO"
        python main.py add-note --prospect-id 1 --user jdoe --type MEETING --text "Capability briefing scheduled"
    """
    setup_logging()
    from etl.prospect_manager import ProspectManager

    mgr = ProspectManager()
    try:
        note_id = mgr.add_note(prospect_id, user, note_type.upper(), text)
        click.echo(f"Added {note_type.upper()} note (note_id={note_id}) to prospect {prospect_id}")
    except ValueError as e:
        click.echo(f"ERROR: {e}")
        sys.exit(1)
    except Exception as e:
        click.echo(f"ERROR: {e}")
        sys.exit(1)


@cli.command("add-team-member")
@click.option("--prospect-id", required=True, type=int, help="Prospect ID")
@click.option("--uei", required=True, help="Entity UEI (SAM)")
@click.option("--role", required=True,
              type=click.Choice(["PRIME", "SUB", "MENTOR", "JV_PARTNER"], case_sensitive=False),
              help="Team role")
@click.option("--notes", default=None, help="Optional notes about this partner")
def add_team_member(prospect_id, uei, role, notes):
    """Add a teaming partner to a prospect.

    The UEI is validated against the entity table but the team member is
    added even if not found (with a warning).

    Examples:
        python main.py add-team-member --prospect-id 1 --uei ABC123DEF456 --role SUB
        python main.py add-team-member --prospect-id 1 --uei XYZ789GHI012 --role JV_PARTNER --notes "Strong past performance"
    """
    setup_logging()
    from etl.prospect_manager import ProspectManager

    mgr = ProspectManager()
    try:
        member_id = mgr.add_team_member(prospect_id, uei, role.upper(), notes=notes)
        click.echo(f"Added team member (id={member_id}) UEI={uei} role={role.upper()} to prospect {prospect_id}")
    except ValueError as e:
        click.echo(f"ERROR: {e}")
        sys.exit(1)
    except Exception as e:
        click.echo(f"ERROR: {e}")
        sys.exit(1)


@cli.command("save-search")
@click.option("--name", required=True, help="Search name")
@click.option("--user", required=True, help="Username who owns this search")
@click.option("--set-asides", default=None, help="Comma-separated set-aside codes (e.g., WOSB,EDWOSB)")
@click.option("--naics", default=None, help="Comma-separated NAICS codes")
@click.option("--states", default=None, help="Comma-separated state codes")
@click.option("--min-value", default=None, type=float, help="Minimum award amount")
@click.option("--max-value", default=None, type=float, help="Maximum award amount")
@click.option("--types", default=None, help="Comma-separated opportunity types (o,k,p)")
@click.option("--days-back", default=None, type=int, help="Only posted in last N days")
@click.option("--open-only", is_flag=True, default=False, help="Only open opportunities")
@click.option("--description", default=None, help="Optional description")
def save_search(name, user, set_asides, naics, states, min_value, max_value,
                types, days_back, open_only, description):
    """Save a reusable search filter for opportunities.

    Build a filter set from the provided options and store it as a saved
    search in the database. Use 'run-search' to execute later.

    Examples:
        python main.py save-search --name "WOSB IT Midwest" --user jdoe --set-asides WOSB,EDWOSB --naics 541511,541512 --states WI,IL,MN --open-only
        python main.py save-search --name "Big 8A" --user jdoe --set-asides 8A,8AN --min-value 500000
    """
    setup_logging()
    from etl.prospect_manager import ProspectManager

    # Build filter criteria dict
    criteria = {}
    if set_asides:
        criteria["set_aside_codes"] = [s.strip() for s in set_asides.split(",")]
    if naics:
        criteria["naics_codes"] = [s.strip() for s in naics.split(",")]
    if states:
        criteria["states"] = [s.strip().upper() for s in states.split(",")]
    if min_value is not None:
        criteria["min_award_amount"] = min_value
    if max_value is not None:
        criteria["max_award_amount"] = max_value
    if types:
        criteria["types"] = [s.strip() for s in types.split(",")]
    if days_back is not None:
        criteria["days_back"] = days_back
    if open_only:
        criteria["open_only"] = True

    if not criteria:
        click.echo("ERROR: At least one filter option is required (--set-asides, --naics, --states, etc.)")
        sys.exit(1)

    mgr = ProspectManager()
    try:
        import json
        click.echo(f"Filter criteria: {json.dumps(criteria, indent=2)}")
        search_id = mgr.save_search(name, user, criteria, description=description)
        click.echo(f"Saved search '{name}' (search_id={search_id})")
    except ValueError as e:
        click.echo(f"ERROR: {e}")
        sys.exit(1)
    except Exception as e:
        click.echo(f"ERROR: {e}")
        sys.exit(1)


@cli.command("run-search")
@click.option("--name", default=None, help="Search name")
@click.option("--id", "search_id", default=None, type=int, help="Search ID")
@click.option("--limit", "result_limit", default=50, type=int, help="Max results to display (default: 50)")
def run_search(name, search_id, result_limit):
    """Execute a saved search against the opportunity table.

    Runs the saved filter criteria against the opportunity table and
    displays matching results. Updates last_run_at on the saved search.

    Examples:
        python main.py run-search --name "WOSB IT Midwest"
        python main.py run-search --id 1
    """
    setup_logging()
    from etl.prospect_manager import ProspectManager

    if not name and not search_id:
        click.echo("ERROR: Either --name or --id is required")
        sys.exit(1)

    mgr = ProspectManager()
    try:
        result = mgr.run_search(search_id=search_id, search_name=name)
    except ValueError as e:
        click.echo(f"ERROR: {e}")
        sys.exit(1)
    except Exception as e:
        click.echo(f"ERROR: {e}")
        sys.exit(1)

    search_info = result["search"]
    results = result["results"]
    new_count = result["new_count"]

    click.echo(f"\nSearch: {search_info['search_name']}")
    click.echo(f"Results: {result['count']} total, {new_count} new since last run")
    if search_info.get("last_run_at"):
        click.echo(f"Previous run: {search_info['last_run_at']}")

    if not results:
        click.echo("No matching opportunities found.")
        return

    display = results[:result_limit]
    click.echo(f"\n{'Title':<50s}  {'Set-Aside':>9s}  {'NAICS':>6s}  {'Deadline':>12s}  {'State':>5s}  {'Active':>6s}")
    click.echo("-" * 100)

    from datetime import datetime as dt_cls
    for r in display:
        title = r.get("title") or ""
        title_str = (title[:47] + "...") if len(title) > 50 else title

        deadline = r.get("response_deadline")
        if deadline:
            if hasattr(deadline, "strftime"):
                deadline_str = deadline.strftime("%Y-%m-%d")
            else:
                deadline_str = str(deadline)[:10]
        else:
            deadline_str = "N/A"

        click.echo(
            f"{title_str:<50s}  {(r.get('set_aside_code') or ''):>9s}  "
            f"{(r.get('naics_code') or ''):>6s}  {deadline_str:>12s}  "
            f"{(r.get('pop_state') or ''):>5s}  {(r.get('active') or ''):>6s}"
        )

    if len(results) > result_limit:
        click.echo(f"\n  ... and {len(results) - result_limit} more (use --limit to show more)")

    click.echo("")


@cli.command("list-searches")
@click.option("--user", default=None, help="Filter by username")
def list_searches(user):
    """List saved searches.

    Examples:
        python main.py list-searches
        python main.py list-searches --user jdoe
    """
    setup_logging()
    from etl.prospect_manager import ProspectManager

    mgr = ProspectManager()
    searches = mgr.list_saved_searches(username=user)

    if not searches:
        click.echo("No saved searches found.")
        return

    click.echo(f"\n{'ID':>4s}  {'Name':<30s}  {'User':<15s}  {'Last Run':>19s}  {'New':>4s}  {'Active':>6s}")
    click.echo("-" * 90)
    for s in searches:
        last_run = s.get("last_run_at")
        if last_run:
            if hasattr(last_run, "strftime"):
                last_run_str = last_run.strftime("%Y-%m-%d %H:%M:%S")
            else:
                last_run_str = str(last_run)
        else:
            last_run_str = "never"

        new_str = str(s.get("last_new_results") or 0)

        click.echo(
            f"{s['search_id']:>4d}  {s['search_name']:<30s}  {s['username']:<15s}  "
            f"{last_run_str:>19s}  {new_str:>4s}  {s['is_active']:>6s}"
        )

    click.echo(f"\nTotal: {len(searches)} search(es)")


@cli.command("dashboard")
def dashboard():
    """Show the prospect pipeline dashboard.

    Displays summary counts by status, upcoming deadlines, workload
    by assignee, win/loss statistics, and saved search info.
    """
    setup_logging()
    from etl.prospect_manager import ProspectManager

    mgr = ProspectManager()
    try:
        data = mgr.get_dashboard_data()
    except Exception as e:
        click.echo(f"ERROR: Could not load dashboard data: {e}")
        sys.exit(1)

    click.echo(f"\n{'='*60}")
    click.echo(f"  PROSPECT PIPELINE DASHBOARD")
    click.echo(f"{'='*60}")

    # By status
    by_status = data.get("by_status", {})
    total_open = data.get("total_open", 0)
    click.echo(f"\n  --- Pipeline ({total_open} open) ---")
    status_order = ["NEW", "REVIEWING", "PURSUING", "BID_SUBMITTED", "WON", "LOST", "DECLINED", "NO_BID"]
    for s in status_order:
        cnt = by_status.get(s, 0)
        if cnt > 0:
            bar = "#" * min(cnt, 30)
            click.echo(f"    {s:<15s} {cnt:>4d}  {bar}")

    # Due this week
    due = data.get("due_this_week", [])
    click.echo(f"\n  --- Due This Week ({len(due)}) ---")
    if due:
        for d in due:
            deadline = d.get("response_deadline")
            if hasattr(deadline, "strftime"):
                deadline_str = deadline.strftime("%Y-%m-%d")
            else:
                deadline_str = str(deadline)[:10] if deadline else "N/A"

            title = d.get("title") or ""
            title_str = (title[:35] + "...") if len(title) > 38 else title
            click.echo(
                f"    #{d['prospect_id']:<4d} {d['priority']:<8s} {deadline_str}  "
                f"{(d.get('assigned_to') or ''):<10s} {title_str}"
            )
    else:
        click.echo("    (none)")

    # By assignee
    by_assignee = data.get("by_assignee", [])
    click.echo(f"\n  --- Workload by Assignee ---")
    if by_assignee:
        for a in by_assignee:
            bar = "#" * min(a["cnt"], 30)
            click.echo(
                f"    {a['username']:<15s} ({a['display_name']:<20s}) {a['cnt']:>3d}  {bar}"
            )
    else:
        click.echo("    (no assignments)")

    # Win/loss stats
    wl = data.get("win_loss", {})
    click.echo(f"\n  --- Outcomes ---")
    if wl:
        for outcome, cnt in wl.items():
            click.echo(f"    {outcome:<15s} {cnt:>4d}")
        won = wl.get("WON", 0)
        lost = wl.get("LOST", 0)
        if won + lost > 0:
            win_rate = (won / (won + lost)) * 100
            click.echo(f"    Win rate: {win_rate:.1f}% ({won}/{won + lost})")
    else:
        click.echo("    (no outcomes yet)")

    # Saved searches
    searches = data.get("saved_searches", [])
    click.echo(f"\n  --- Saved Searches ({len(searches)}) ---")
    if searches:
        for s in searches:
            last_run = s.get("last_run_at")
            if last_run:
                if hasattr(last_run, "strftime"):
                    run_str = last_run.strftime("%Y-%m-%d %H:%M")
                else:
                    run_str = str(last_run)[:16]
            else:
                run_str = "never"
            new_str = f"{s.get('last_new_results', 0)} new" if s.get("last_new_results") else ""
            click.echo(
                f"    {s['search_name']:<30s}  {s['username']:<12s}  last run: {run_str}  {new_str}"
            )
    else:
        click.echo("    (none)")

    click.echo(f"\n{'='*60}\n")


if __name__ == "__main__":
    cli()
