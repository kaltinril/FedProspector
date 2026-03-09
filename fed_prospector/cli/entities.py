"""Entity data CLI commands.

Commands: load-entities, search-entities
"""

import sys
from pathlib import Path

import click

from config.logging_config import setup_logging
from config import settings


# API filter option names (used to detect when filters are passed with non-api types)
_API_FILTER_OPTS = ("uei", "entity_name", "naics", "set_aside", "status", "max_calls")


@click.command("load-entities")
@click.option("--type", "load_type", type=click.Choice(["monthly", "api"]), default="api",
              help="Load method: monthly (full bulk extract), api (paginated API query)")
@click.option("--date", "load_date", default=None, help="Date for --type=api (YYYY-MM-DD, default: today)")
@click.option("--year", type=int, default=None, help="Year for monthly extract (default: current)")
@click.option("--month", type=int, default=None, help="Month for monthly extract (default: current)")
@click.option("--file", "file_path", default=None, help="Load from local file (skip download)")
@click.option("--key", "api_key_number", type=click.Choice(["1", "2"]), default="1",
              help="SAM.gov API key: 1 (10/day) or 2 (1000/day)")
# API filters (--type=api only):
@click.option("--uei", default=None, help="Filter by UEI (exact match, --type=api only)")
@click.option("--name", "entity_name", default=None, help="Filter by entity name (partial match, --type=api only)")
@click.option("--naics", default=None, help="NAICS codes, comma-separated (--type=api only)")
@click.option("--set-aside", default=None, help="Business type code: 8W=WOSB, 8E=EDWOSB, A4=8(a) (--type=api only)")
@click.option("--status", default=None, help="Registration status A=active, E=expired (--type=api only, default: A)")
@click.option("--max-calls", default=None, type=int, help="Max API calls safety cap (--type=api only, default: 100)")
@click.option("--force", is_flag=True, default=False, help="Force reload even if already loaded")
def load_entities(load_type, load_date, year, month, file_path, api_key_number,
                  uei, entity_name, naics, set_aside, status, max_calls, force):
    """Load SAM.gov entity data into the database.

    Supports two load methods:

      api     (default) - Query Entity Management API with filters (date=today if no filters)
      monthly           - Download monthly bulk extract ZIP, load DAT via LOAD DATA INFILE

    Use --file to load from a local file (auto-detects .dat vs .json format).

    Examples:
        python main.py load entities
        python main.py load entities --type=api --date=2026-03-05
        python main.py load entities --type=monthly
        python main.py load entities --type=api --naics=541512 --set-aside=8W --key=2
        python main.py load entities --file=data/downloads/SAM_PUBLIC_MONTHLY_V2_202603.dat
    """
    logger = setup_logging()

    if not settings.SAM_API_KEY or settings.SAM_API_KEY == "your_api_key_here":
        click.echo("ERROR: SAM_API_KEY not configured in .env file")
        sys.exit(1)

    key_num = int(api_key_number)

    # --file takes priority over --type: auto-detect format
    if file_path:
        _load_from_file(logger, file_path)
        return

    # Warn if API filter options are passed with non-api types
    if load_type != "api":
        used_filters = [
            opt for opt in _API_FILTER_OPTS
            if locals().get(opt) is not None
        ]
        if used_filters:
            click.echo(f"WARNING: Filter options only apply to --type=api. Ignoring: {', '.join('--' + o.replace('_', '-') for o in used_filters)}")

    if load_type == "monthly":
        _load_monthly(logger, year, month, key_num)
    elif load_type == "api":
        _load_via_api(logger, load_date, key_num, force, max_calls,
                      uei=uei, entity_name=entity_name, naics=naics,
                      set_aside=set_aside, status=status)


# =====================================================================
# Helper: load from local file
# =====================================================================

def _load_from_file(logger, file_path):
    """Load entities from a local .dat or .json file."""
    fp = Path(file_path)
    if not fp.exists():
        click.echo(f"ERROR: File not found: {file_path}")
        sys.exit(1)

    file_ext = fp.suffix.lower()

    if file_ext == ".dat":
        from etl.dat_parser import parse_dat_file, get_dat_record_count
        from etl.bulk_loader import BulkLoader

        try:
            record_count = get_dat_record_count(str(fp))
            click.echo(f"Loading DAT file: {fp.name}")
            click.echo(f"  Records in file (from header): {record_count:,d}")
            click.echo(f"  Method: LOAD DATA INFILE (bulk)")
        except ValueError as e:
            click.echo(f"WARNING: Could not read DAT header: {e}")
            click.echo(f"Loading DAT file: {fp.name}")

        loader = BulkLoader()
        try:
            entity_iter = parse_dat_file(str(fp))
            stats = loader.bulk_load_entities(
                entity_iter,
                source_file=str(fp),
                load_type="FULL",
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
        # JSON file: use streaming loader with change detection
        from etl.entity_loader import EntityLoader

        click.echo(f"Loading JSON file: {fp.name}")
        click.echo(f"  Mode: incremental")

        loader = EntityLoader()
        try:
            stats = loader.load_from_json_extract(str(fp), mode="incremental")
            _print_json_load_stats(stats)
        except Exception as e:
            logger.exception("Entity load failed")
            click.echo(f"\nERROR: {e}")
            sys.exit(1)


# =====================================================================
# Helper: monthly extract (download ZIP + load DAT)
# =====================================================================

def _load_monthly(logger, year, month, api_key_number):
    """Download monthly bulk extract and load via LOAD DATA INFILE."""
    from datetime import date as date_cls
    from api_clients.sam_extract_client import SAMExtractClient

    today = date_cls.today()
    year = year or today.year
    month = month or today.month

    api_key = settings.SAM_API_KEY if api_key_number == 1 else settings.SAM_API_KEY_2
    client = SAMExtractClient(api_key=api_key)
    click.echo(f"Downloading monthly extract for {year}-{month:02d}...")
    click.echo(f"  API key: {api_key_number} | Calls remaining: {client._get_remaining_requests()}")

    try:
        paths = client.download_monthly_extract(year, month)
        click.echo(f"\nExtracted files:")
        for p in paths:
            click.echo(f"  {p}")
    except Exception as e:
        click.echo(f"ERROR during download: {e}")
        sys.exit(1)

    # ---- Load each extracted file ----
    click.echo(f"\nLoading {len(paths)} file(s)...")

    for fp in paths:
        fp = Path(fp)
        file_ext = fp.suffix.lower()

        if file_ext == ".dat":
            from etl.dat_parser import parse_dat_file, get_dat_record_count
            from etl.bulk_loader import BulkLoader

            try:
                record_count = get_dat_record_count(str(fp))
                click.echo(f"\nLoading DAT file: {fp.name}")
                click.echo(f"  Records in file (from header): {record_count:,d}")
                click.echo(f"  Method: LOAD DATA INFILE (bulk)")
            except ValueError as e:
                click.echo(f"WARNING: Could not read DAT header: {e}")
                click.echo(f"\nLoading DAT file: {fp.name}")

            loader = BulkLoader()
            try:
                entity_iter = parse_dat_file(str(fp))
                stats = loader.bulk_load_entities(
                    entity_iter,
                    source_file=str(fp),
                    load_type="FULL",
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
            from etl.entity_loader import EntityLoader
            click.echo(f"\nLoading JSON file: {fp.name}")
            loader = EntityLoader()
            try:
                stats = loader.load_from_json_extract(str(fp), mode="full")
                _print_json_load_stats(stats)
            except Exception as e:
                logger.exception("Entity load failed")
                click.echo(f"\nERROR: {e}")
                sys.exit(1)

    # ---- Clean up extracted DAT files ----
    for fp in paths:
        fp = Path(fp)
        if fp.suffix.lower() == ".dat" and fp.exists():
            try:
                size_mb = fp.stat().st_size / (1024 * 1024)
                fp.unlink()
                logger.info("Cleaned up extracted DAT file: %s (%.1f MB)", fp.name, size_mb)
                click.echo(f"  Cleaned up: {fp.name} ({size_mb:.1f} MB freed)")
            except OSError as e:
                logger.warning("Could not delete DAT file %s: %s", fp.name, e)
                click.echo(f"  WARNING: Could not delete {fp.name}: {e}")

    click.echo(f"\nMonthly refresh complete! ({len(paths)} file(s) processed)")


# =====================================================================
# Helper: API-based loading with filters
# =====================================================================

def _load_via_api(logger, load_date, api_key_number, force=False, max_calls=None,
                  uei=None, entity_name=None, naics=None, set_aside=None, status=None):
    """Query Entity Management API with filters and load results."""
    from datetime import date as date_cls
    import json as _json
    from api_clients.sam_entity_client import SAMEntityClient
    from api_clients.base_client import RateLimitExceeded
    from etl.entity_loader import EntityLoader
    from etl.load_manager import LoadManager
    from db.connection import get_connection

    # Default max_calls for api type
    if max_calls is None:
        max_calls = 100

    # Parse date
    if not load_date:
        d = date_cls.today()
    else:
        try:
            d = date_cls.fromisoformat(load_date)
        except ValueError:
            click.echo(f"ERROR: Invalid date format: {load_date} (use YYYY-MM-DD)")
            sys.exit(1)

    # Determine if this is a date-only query (use iter_entity_pages_by_date with resume)
    has_filters = any([uei, entity_name, naics, set_aside])
    date_only = not has_filters

    if date_only:
        # Use the page-by-page approach with resume support
        _load_via_api_by_date(logger, d, api_key_number, force, max_calls, status)
    else:
        # Use search_entities with filters
        _load_via_api_filtered(logger, d, api_key_number, max_calls,
                               uei=uei, entity_name=entity_name, naics=naics,
                               set_aside=set_aside, status=status)


def _load_via_api_by_date(logger, d, api_key_number, force, max_calls, status):
    """API load using iter_entity_pages_by_date with resume support.

    Reuses the proven page-by-page resume logic from the old _refresh_daily.
    """
    import json as _json
    from api_clients.sam_entity_client import SAMEntityClient
    from api_clients.base_client import RateLimitExceeded
    from etl.entity_loader import EntityLoader
    from etl.load_manager import LoadManager
    from db.connection import get_connection

    reg_status = status or "A"

    # ---- Check previous loads for this date (resume support) ----
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT load_id, status, records_inserted, records_updated, parameters "
            "FROM etl_load_log "
            "WHERE source_system = 'SAM_ENTITY' "
            "AND parameters LIKE %s "
            "ORDER BY CAST(JSON_EXTRACT(parameters, '$.pages_fetched') AS UNSIGNED) DESC "
            "LIMIT 1",
            (f'%"update_date": "{d.isoformat()}"%',),
        )
        prev_load = cursor.fetchone()
    finally:
        cursor.close()
        conn.close()

    resume_page = 0
    if prev_load and not force:
        prev_params = _json.loads(prev_load["parameters"]) if prev_load["parameters"] else {}
        prev_total = prev_params.get("total_records")
        prev_pages = prev_params.get("pages_fetched", 0)
        is_complete = prev_params.get("complete", False)

        if is_complete:
            click.echo(f"Already loaded all entities for {d} (load_id={prev_load['load_id']}: "
                        f"{prev_load['records_inserted']} inserted, "
                        f"{prev_load['records_updated']} updated). Skipping.")
            click.echo("  Use --force to reload from scratch.")
            return

        if prev_pages > 0:
            resume_page = prev_pages
            click.echo(f"Resuming from page {resume_page} "
                        f"(previous run loaded {prev_pages} pages, "
                        f"~{prev_pages * 10} of {prev_total or '?'} entities).")

    # ---- Set up client ----
    client = SAMEntityClient(api_key_number=api_key_number)
    remaining = client._get_remaining_requests()
    click.echo(f"Querying Entity Management API for entities updated on {d}...")
    click.echo(f"  API key: {api_key_number} | Calls remaining: {remaining}")

    if remaining <= 0:
        click.echo("ERROR: No API calls remaining for today.")
        sys.exit(1)

    if max_calls:
        click.echo(f"  Max API calls: {max_calls} (~{max_calls * 10} entities)")

    # ---- Create load entry and process page by page ----
    load_mgr = LoadManager()
    loader = EntityLoader()
    load_id = load_mgr.start_load(
        source_system="SAM_ENTITY", load_type="INCREMENTAL",
        parameters={
            "update_date": d.isoformat(),
            "pages_fetched": resume_page,
            "total_records": None,
            "complete": False,
        },
    )

    pages_fetched_total = resume_page
    total_records = None
    cumulative = {
        "records_read": 0, "records_inserted": 0, "records_updated": 0,
        "records_unchanged": 0, "records_errored": 0,
    }
    rate_limited = False

    try:
        for page_entities, page_num, total in client.iter_entity_pages_by_date(
            d, registration_status=reg_status,
            start_page=resume_page, max_pages=max_calls,
        ):
            total_records = total

            # Upsert this page's entities
            if page_entities:
                page_stats = loader.load_entity_batch(page_entities, load_id)
                for k in cumulative:
                    cumulative[k] += page_stats.get(k, 0)

            pages_fetched_total = page_num + 1  # page_num is 0-based
            is_complete = (
                total_records is not None
                and (pages_fetched_total * 10) >= total_records
            )

            # Save progress after each page (survives ctrl+c / kill)
            load_mgr.save_load_progress(
                load_id,
                parameters={
                    "update_date": d.isoformat(),
                    "pages_fetched": pages_fetched_total,
                    "total_records": total_records,
                    "complete": is_complete,
                },
                **cumulative,
            )

            click.echo(
                f"  Page {page_num}: {len(page_entities)} entities "
                f"({pages_fetched_total}/{(total_records + 9) // 10 if total_records else '?'} pages)"
            )

    except KeyboardInterrupt:
        new_pages = pages_fetched_total - resume_page
        click.echo(f"\n  Interrupted. {new_pages} new page(s) saved.")
        click.echo("  Run the same command again to continue.")
        return
    except RateLimitExceeded:
        rate_limited = True
        click.echo(f"  Rate limit reached after {pages_fetched_total - resume_page} new pages.")
    except Exception as e:
        if isinstance(getattr(e, '__context__', None), KeyboardInterrupt):
            new_pages = pages_fetched_total - resume_page
            click.echo(f"\n  Interrupted. {new_pages} new page(s) saved.")
            click.echo("  Run the same command again to continue.")
            return
        if "429" in str(e):
            rate_limited = True
            click.echo(f"  Server rate limit (429) after {pages_fetched_total - resume_page} new pages.")
            if api_key_number == 1:
                click.echo("  Tip: Use --key=2 for the 1000/day tier.")
        else:
            load_mgr.fail_load(load_id, str(e))
            logger.exception("Entity API query failed")
            click.echo(f"\nERROR: {e}")
            sys.exit(1)

    # ---- Handle edge case: no new pages fetched ----
    if pages_fetched_total == resume_page:
        load_mgr.save_load_progress(
            load_id,
            parameters={
                "update_date": d.isoformat(),
                "pages_fetched": pages_fetched_total,
                "total_records": total_records,
                "complete": False,
            },
            **cumulative,
        )
        if rate_limited:
            click.echo("Rate limited before any new pages could be fetched.")
            click.echo(f"  Will resume from page {resume_page} next time.")
        else:
            click.echo(f"No entities updated on {d}.")
        return

    # ---- Summary ----
    is_complete = (
        total_records is not None
        and (pages_fetched_total * 10) >= total_records
    )
    load_status = "COMPLETE" if is_complete else f"PARTIAL ({pages_fetched_total} of {(total_records + 9) // 10 if total_records else '?'} pages)"
    remaining_after = client._get_remaining_requests()
    click.echo(f"\nAPI load {load_status}!")
    _print_json_load_stats(cumulative)
    click.echo(f"  API calls remaining: {remaining_after}")
    if not is_complete:
        click.echo("  Run the same command again to continue.")


def _load_via_api_filtered(logger, d, api_key_number, max_calls,
                            uei=None, entity_name=None, naics=None,
                            set_aside=None, status=None):
    """API load using search_entities with specific filters."""
    from api_clients.sam_entity_client import SAMEntityClient
    from etl.entity_loader import EntityLoader

    reg_status = status or "A"

    # Build base filters
    base_filters = {"registrationStatus": reg_status}

    if uei:
        base_filters["ueiSAM"] = uei
    if entity_name:
        base_filters["legalBusinessName"] = entity_name
    if set_aside:
        if set_aside == "A4":
            base_filters["sbaBusinessTypeCode"] = set_aside
        else:
            base_filters["businessTypeCode"] = set_aside

    # Format date for SAM.gov (MM/DD/YYYY)
    base_filters["updateDate"] = d.strftime("%m/%d/%Y")

    # Build list of query sets (one per NAICS code, or one if no NAICS)
    if naics:
        naics_codes = [c.strip() for c in naics.split(",") if c.strip()]
    else:
        naics_codes = [None]

    client = SAMEntityClient(api_key_number=api_key_number)
    remaining = client._get_remaining_requests()
    click.echo(f"Querying Entity Management API with filters...")
    click.echo(f"  API key: {api_key_number} | Calls remaining: {remaining}")
    click.echo(f"  Filters: {base_filters}")
    if naics and len(naics_codes) > 1:
        click.echo(f"  NAICS codes: {', '.join(naics_codes)} ({len(naics_codes)} separate queries)")
    click.echo(f"  Max API calls: {max_calls}")

    if remaining <= 0:
        click.echo("ERROR: No API calls remaining for today.")
        sys.exit(1)

    loader = EntityLoader()
    all_entities = []
    calls_used = 0

    for naics_code in naics_codes:
        if calls_used >= max_calls:
            click.echo(f"  Reached max API calls ({max_calls}). Stopping.")
            break

        filters = dict(base_filters)
        if naics_code:
            filters["naicsCode"] = naics_code
            click.echo(f"\n  Querying NAICS {naics_code}...")

        page_count = 0
        try:
            for entity in client.search_entities(**filters):
                all_entities.append(entity)
                # Approximate calls used (10 entities per page)
                if len(all_entities) % 10 == 0:
                    page_count += 1
                    calls_used += 1
                    click.echo(f"    Page {page_count}: {len(all_entities)} entities so far")
                    if calls_used >= max_calls:
                        click.echo(f"  Reached max API calls ({max_calls}). Stopping.")
                        break
        except Exception as e:
            if "429" in str(e):
                click.echo(f"  Rate limit reached after {len(all_entities)} entities.")
                break
            raise

    if not all_entities:
        click.echo("\nNo entities matched the filters.")
        return

    click.echo(f"\nLoading {len(all_entities)} entities...")
    try:
        stats = loader.load_from_api_response(
            all_entities,
            mode="incremental",
            extra_parameters={
                "source": "api_filtered",
                "filters": base_filters,
                "naics_codes": naics if naics else None,
            },
        )
        _print_json_load_stats(stats)
    except Exception as e:
        logger.exception("Entity API load failed")
        click.echo(f"\nERROR: {e}")
        sys.exit(1)

    remaining_after = client._get_remaining_requests()
    click.echo(f"  API calls remaining: {remaining_after}")


# =====================================================================
# Stats printer (shared by all load types)
# =====================================================================

def _print_json_load_stats(stats):
    """Print load statistics for JSON/API entity loads."""
    click.echo(f"\nLoad complete!")
    click.echo(f"  Records read:      {stats.get('records_read', 0):>10,d}")
    click.echo(f"  Records inserted:  {stats.get('records_inserted', 0):>10,d}")
    click.echo(f"  Records updated:   {stats.get('records_updated', 0):>10,d}")
    click.echo(f"  Records unchanged: {stats.get('records_unchanged', 0):>10,d}")
    click.echo(f"  Records errored:   {stats.get('records_errored', 0):>10,d}")


# =====================================================================
# search-entities command (unchanged)
# =====================================================================

@click.command("search-entities")
@click.option("--uei", default=None, help="Filter by UEI (exact match)")
@click.option("--name", default=None, help="Filter by entity name (partial match)")
@click.option("--naics", default=None, help="Filter by NAICS code")
@click.option("--state", default=None, help="Filter by state code (e.g. VA, MD)")
@click.option("--cert", default=None, help="Filter by SBA certification type (WOSB, 8A, HUBZone, SDVOSB)")
@click.option("--active-only", is_flag=True, default=False, help="Only show active registrations")
@click.option("--limit", default=25, type=int, help="Max results to show (default: 25)")
def search_entities(uei, name, naics, state, cert, active_only, limit):
    """Search loaded entities in the local database.

    Queries the entity table (no API calls). Results are ordered by
    entity name.

    Examples:
        python main.py search entities --name "Acme"
        python main.py search entities --naics 541512 --state VA
        python main.py search entities --cert WOSB --active-only
        python main.py search entities --uei ABC123DEF456
    """
    logger = setup_logging()
    from db.connection import get_connection

    conn = get_connection()
    cursor = conn.cursor()

    try:
        where_clauses = []
        params = []

        if uei:
            where_clauses.append("e.uei_sam = %s")
            params.append(uei)

        if name:
            where_clauses.append("e.legal_business_name LIKE %s")
            params.append(f"%{name}%")

        if naics:
            where_clauses.append(
                "EXISTS (SELECT 1 FROM entity_naics en "
                "WHERE en.uei_sam = e.uei_sam AND en.naics_code = %s)"
            )
            params.append(naics)

        if state:
            where_clauses.append(
                "EXISTS (SELECT 1 FROM entity_address ea2 "
                "WHERE ea2.uei_sam = e.uei_sam AND ea2.state_or_province = %s)"
            )
            params.append(state)

        if cert:
            where_clauses.append(
                "EXISTS (SELECT 1 FROM entity_sba_certification ec "
                "WHERE ec.uei_sam = e.uei_sam AND ec.sba_type_code = %s "
                "AND (ec.certification_exit_date IS NULL OR ec.certification_exit_date > CURDATE()))"
            )
            params.append(cert)

        if active_only:
            where_clauses.append("e.registration_status = 'A'")

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        sql = (
            "SELECT /*+ NO_INDEX(e idx_entity_name) */ e.uei_sam, e.legal_business_name, e.cage_code, e.primary_naics, "
            "  e.registration_status, e.registration_expiration_date, "
            "  e.pop_state "
            "FROM v_entity_search e "
            f"{where_sql} "
            "ORDER BY e.legal_business_name "
            "LIMIT %s"
        )
        params.append(limit)

        cursor.execute(sql, params)
        rows = cursor.fetchall()

        if not rows:
            click.echo("No entities found matching the criteria.")
            filter_parts = []
            if uei:
                filter_parts.append(f"uei={uei}")
            if name:
                filter_parts.append(f"name={name}")
            if naics:
                filter_parts.append(f"naics={naics}")
            if state:
                filter_parts.append(f"state={state}")
            if cert:
                filter_parts.append(f"cert={cert}")
            if active_only:
                filter_parts.append("active-only")
            click.echo(f"  Filters: {', '.join(filter_parts) if filter_parts else 'none'}")
            return

        click.echo(f"\nFound {len(rows)} entities"
                   + (f" (showing top {limit})" if len(rows) == limit else ""))
        click.echo("")

        header = (
            f"{'UEI':<12s}  {'Name':<40s}  {'CAGE':<5s}  {'State':<5s}  "
            f"{'NAICS':<6s}  {'Expires':<10s}"
        )
        click.echo(header)
        click.echo("-" * len(header))

        for row in rows:
            uei_val, biz_name, cage, primary_naics, reg_status, reg_exp, state_val = row

            uei_str = f"{(uei_val or ''):<12s}"
            name_trunc = (biz_name[:37] + "...") if biz_name and len(biz_name) > 40 else (biz_name or "")
            name_str = f"{name_trunc:<40s}"
            cage_str = f"{(cage or ''):<5s}"
            state_str = f"{(state_val or ''):<5s}"
            naics_str = f"{(primary_naics or ''):<6s}"

            if reg_exp:
                exp_str = str(reg_exp)[:10]
            else:
                exp_str = "N/A"
            exp_str = f"{exp_str:<10s}"

            click.echo(f"{uei_str}  {name_str}  {cage_str}  {state_str}  {naics_str}  {exp_str}")

        click.echo("")
        click.echo("Note: Run 'python main.py load entities' to refresh local data.")

    except Exception as e:
        logger.exception("Entity search failed")
        click.echo(f"ERROR: {e}")
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()
