"""Database management CLI commands.

Commands: build-database, load-lookups, status, check-api, seed-quality-rules
"""

import sys
from pathlib import Path

import click

from config.logging_config import setup_logging
from config import settings


def _split_sql_statements(sql: str) -> list[str]:
    """Split SQL text on semicolons, respecting single-quoted strings.

    Naive split(';') breaks on SEPARATOR '; ' inside GROUP_CONCAT etc.
    This walks the string and only splits on semicolons outside quotes.
    """
    statements = []
    current = []
    in_quote = False

    for char in sql:
        if char == "'" and not in_quote:
            in_quote = True
            current.append(char)
        elif char == "'" and in_quote:
            in_quote = False
            current.append(char)
        elif char == ";" and not in_quote:
            stmt = "".join(current).strip()
            if stmt:
                statements.append(stmt)
            current = []
        else:
            current.append(char)

    # Last fragment (no trailing semicolon)
    stmt = "".join(current).strip()
    if stmt:
        statements.append(stmt)

    return statements


def _seed_quality_rules_impl(conn):
    """Insert quality rules into etl_data_quality_rule. Truncates first.

    Does NOT commit -- caller is responsible for commit.

    Returns the number of rules inserted.
    """
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
    finally:
        cursor.close()

    return len(rules)


@click.command("build-database")
@click.option("--drop-first", is_flag=True, default=False,
              help="Drop and recreate all tables (DESTROYS DATA)")
def build_database(drop_first):
    """Create all database tables from SQL schema files.

    Safe to run multiple times - uses CREATE TABLE IF NOT EXISTS.
    Use --drop-first to rebuild from scratch (destroys all data).
    """
    logger = setup_logging()

    from db.connection import get_connection

    schema_dir = Path(__file__).parent.parent / "db" / "schema"

    # Process schema in dependency order: tables first, then views, functions, procedures
    sql_files = []
    for subfolder in ["tables", "views", "functions", "procedures"]:
        sub_path = schema_dir / subfolder
        if sub_path.is_dir():
            sql_files.extend(sorted(sub_path.glob("*.sql")))

    if not sql_files:
        logger.error("No SQL files found in %s", schema_dir)
        sys.exit(1)

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
            rel_name = sql_file.relative_to(schema_dir)
            logger.info("Executing: %s", rel_name)
            with open(sql_file, "r", encoding="utf-8") as f:
                sql = f.read()

            # Split on semicolons outside of quoted strings
            for stmt in _split_sql_statements(sql):
                if stmt and not stmt.startswith("--") and not stmt.startswith("USE "):
                    try:
                        cursor.execute(stmt)
                    except Exception as e:
                        logger.warning("Statement warning in %s: %s", rel_name, e)
            conn.commit()
            click.echo(f"  OK: {rel_name}")

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

        # Auto-seed data quality rules
        click.echo("\nSeeding data quality rules...")
        try:
            rule_count = _seed_quality_rules_impl(conn)
            conn.commit()
            click.echo(f"  Quality rules seeded: {rule_count} rules")
        except Exception as e:
            logger.warning("Quality rules seeding failed (non-fatal): %s", e)
            click.echo(f"  WARNING: Quality rules seeding failed: {e}")

    except Exception as e:
        conn.rollback()
        logger.error("Database build failed: %s", e)
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()


@click.command("load-lookups")
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
            "entity_structure": loader.load_entity_structures,
            "setaside": loader.load_set_aside_types,
            "sba_type": loader.load_sba_types,
        }
        if table not in method_map:
            click.echo(f"Unknown table: {table}")
            click.echo(f"Available: {', '.join(method_map.keys())}")
            sys.exit(1)

        count = method_map[table]()
        click.echo(f"Loaded {count} rows")


@click.command("status")
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
                      "gsa_labor_rate", "stg_entity_raw", "usaspending_award",
                      "usaspending_transaction", "sam_subaward"):
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


@click.command("check-api")
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


@click.command("seed-quality-rules")
def seed_quality_rules():
    """Seed the etl_data_quality_rule table with initial data quality rules.

    These rules define how the data cleaner handles known SAM.gov data
    quality issues during entity loading.

    Safe to run multiple times - truncates and reloads.
    """
    logger = setup_logging()
    from db.connection import get_connection

    conn = get_connection()
    try:
        count = _seed_quality_rules_impl(conn)
        conn.commit()
        click.echo(f"Seeded {count} data quality rules into etl_data_quality_rule")
    except Exception as e:
        conn.rollback()
        click.echo(f"ERROR: {e}")
        sys.exit(1)
    finally:
        conn.close()
