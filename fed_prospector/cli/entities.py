"""Entity data CLI commands.

Commands: download-extract, load-entities, refresh-entities
"""

import sys
from pathlib import Path

import click

from config.logging_config import setup_logging
from config import settings


@click.command("download-extract")
@click.option("--year", type=int, default=None,
              help="Year for monthly extract (default: current year)")
@click.option("--month", type=int, default=None,
              help="Month for monthly extract (default: current month)")
def download_extract(year, month):
    """Download SAM.gov monthly entity extract file.

    Monthly extracts contain ALL active entities (~867K records, ~143MB ZIP).
    Skips download if the file already exists with the same size.

    For daily incremental updates, use 'entities-refresh --type=daily' instead,
    which queries the Entity Management API directly.

    Examples:
        python main.py load entities-download
        python main.py load entities-download --year=2026 --month=3
    """
    logger = setup_logging()
    from datetime import date as date_cls
    from api_clients.sam_extract_client import SAMExtractClient

    if not settings.SAM_API_KEY or settings.SAM_API_KEY == "your_api_key_here":
        click.echo("ERROR: SAM_API_KEY not configured in .env file")
        sys.exit(1)

    client = SAMExtractClient()
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
        click.echo("\nUse 'python main.py load entities --file=<path>' to load,")
        click.echo("or 'python main.py load entities-refresh --type=monthly' for one-step download+load.")
    except Exception as e:
        click.echo(f"ERROR: {e}")
        sys.exit(1)


@click.command("load-entities")
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
        python main.py load entities --mode=full --file=data/downloads/SAM_PUBLIC_MONTHLY_V2_20260201.dat
        python main.py load entities --mode=daily --file=data/downloads/daily.json
    """
    logger = setup_logging()

    if not file_path:
        click.echo("ERROR: --file is required. Download an extract first:")
        click.echo("  python main.py load entities-download --type=monthly")
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


@click.command("refresh-entities")
@click.option("--type", "extract_type", type=click.Choice(["daily", "monthly"]),
              default="daily", help="Extract type: daily (Entity Management API) or monthly (bulk file)")
@click.option("--year", type=int, default=None,
              help="Year for monthly extract (default: current year)")
@click.option("--month", type=int, default=None,
              help="Month for monthly extract (default: current month)")
@click.option("--date", "extract_date", default=None,
              help="Date for daily refresh (YYYY-MM-DD, default: today)")
@click.option("--key", "api_key_number", type=click.Choice(["1", "2"]), default="1",
              help="SAM.gov API key to use: 1 (10/day) or 2 (1000/day)")
@click.option("--max-calls", default=None, type=int,
              help="Max API calls for daily refresh (10 entities/call)")
@click.option("--force", is_flag=True, default=False,
              help="Force reload even if date was already loaded")
def refresh_entities(extract_type, year, month, extract_date, api_key_number, max_calls, force):
    """Download and load SAM.gov entity data in a single step.

    Monthly: Downloads the bulk extract ZIP, extracts the DAT file,
    loads via LOAD DATA INFILE, then cleans up the DAT.

    Daily: Queries the Entity Management API for entities updated on
    a given date, then upserts them with change detection. Each API
    call returns ~10 entities. Automatically resumes from the last
    page fetched if a previous partial load exists for the same date.

    Examples:
        python main.py load entities-refresh --type=daily
        python main.py load entities-refresh --type=daily --date=2026-03-02 --key=2
        python main.py load entities-refresh --type=monthly
    """
    logger = setup_logging()
    from datetime import date as date_cls

    key_num = int(api_key_number)

    if not settings.SAM_API_KEY or settings.SAM_API_KEY == "your_api_key_here":
        click.echo("ERROR: SAM_API_KEY not configured in .env file")
        sys.exit(1)

    if extract_type == "monthly":
        _refresh_monthly(logger, year, month, key_num)
    else:
        _refresh_daily(logger, extract_date, key_num, force, max_calls)


def _refresh_monthly(logger, year, month, api_key_number):
    """Download monthly bulk extract and load via LOAD DATA INFILE."""
    from datetime import date as date_cls
    from api_clients.sam_extract_client import SAMExtractClient

    today = date_cls.today()
    year = year or today.year
    month = month or today.month

    client = SAMExtractClient()
    click.echo(f"Downloading monthly extract for {year}-{month:02d}...")
    click.echo(f"API calls remaining: {client._get_remaining_requests()}")

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


def _refresh_daily(logger, extract_date, api_key_number, force=False, max_calls=None):
    """Query Entity Management API for entities updated on a date and upsert.

    Processes one page at a time and saves progress to etl_load_log after
    each page.  If killed mid-run, the next invocation resumes from the
    last saved page instead of re-fetching already-loaded data.
    """
    from datetime import date as date_cls
    import json as _json
    from api_clients.sam_entity_client import SAMEntityClient
    from api_clients.base_client import RateLimitExceeded
    from etl.entity_loader import EntityLoader
    from etl.load_manager import LoadManager
    from db.connection import get_connection

    if not extract_date:
        extract_date = date_cls.today().isoformat()
    try:
        d = date_cls.fromisoformat(extract_date)
    except ValueError:
        click.echo(f"ERROR: Invalid date format: {extract_date} (use YYYY-MM-DD)")
        sys.exit(1)

    # ---- Check previous loads for this date (resume support) ----
    # Find the load with the most pages_fetched for this date, regardless of
    # status.  A FAILED load still has committed data for completed pages.
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
            d, start_page=resume_page, max_pages=max_calls,
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
        # Ctrl+C: progress for completed pages is already saved.
        new_pages = pages_fetched_total - resume_page
        click.echo(f"\n  Interrupted. {new_pages} new page(s) saved.")
        click.echo("  Run the same command again to continue.")
        return
    except RateLimitExceeded:
        rate_limited = True
        click.echo(f"  Rate limit reached after {pages_fetched_total - resume_page} new pages.")
    except Exception as e:
        # Ctrl+C during MySQL ops raises InternalError("Unread result found")
        # with KeyboardInterrupt as __context__. Don't mark as FAILED.
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
    status = "COMPLETE" if is_complete else f"PARTIAL ({pages_fetched_total} of {(total_records + 9) // 10 if total_records else '?'} pages)"
    remaining_after = client._get_remaining_requests()
    click.echo(f"\nDaily refresh {status}!")
    _print_json_load_stats(cumulative)
    click.echo(f"  API calls remaining: {remaining_after}")
    if not is_complete:
        click.echo("  Run the same command again to continue.")


def _print_json_load_stats(stats):
    """Print load statistics for JSON/API entity loads."""
    click.echo(f"\nLoad complete!")
    click.echo(f"  Records read:      {stats.get('records_read', 0):>10,d}")
    click.echo(f"  Records inserted:  {stats.get('records_inserted', 0):>10,d}")
    click.echo(f"  Records updated:   {stats.get('records_updated', 0):>10,d}")
    click.echo(f"  Records unchanged: {stats.get('records_unchanged', 0):>10,d}")
    click.echo(f"  Records errored:   {stats.get('records_errored', 0):>10,d}")


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
