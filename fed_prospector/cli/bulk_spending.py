"""CLI command for bulk loading USASpending award data (Phase 44A)."""

from datetime import date, timedelta

import click

from config.logging_config import setup_logging


@click.command("usaspending-bulk")
@click.option("--years-back", default=5, type=int, help="Number of recent fiscal years to load")
@click.option("--fiscal-year", type=int, help="Load a single fiscal year (overrides --years-back)")
@click.option("--days-back", type=int,
              help="Load recent N days of data (uses on-demand API, ignores --source)")
@click.option("--delta", is_flag=True, default=False,
              help="Download and process the monthly delta file instead of a full fiscal year "
                   "archive. Mutually exclusive with --fiscal-year and --years-back.")
@click.option("--skip-download", is_flag=True, help="Use previously downloaded files")
@click.option("--source", type=click.Choice(["archive", "api"]), default="archive",
              help="Download source: archive (pre-built, fast) or api (on-demand, slow)")
@click.option("--fast", is_flag=True, default=False,
              help="Drop secondary indexes before load, rebuild after (faster bulk inserts)")
@click.option("--check-available", is_flag=True, default=False,
              help="List available archive/delta files without downloading or loading")
def usaspending_bulk(years_back, fiscal_year, days_back, delta, skip_download, source, fast,
                     check_available):
    """Bulk load USASpending award data from CSV downloads.

    Downloads fiscal-year bulk CSV archives from USASpending.gov and loads
    them into the usaspending_award table using LOAD DATA INFILE.

    Examples:
        python main.py load usaspending-bulk
        python main.py load usaspending-bulk --fiscal-year 2025
        python main.py load usaspending-bulk --years-back 3
        python main.py load usaspending-bulk --days-back 10
        python main.py load usaspending-bulk --delta
        python main.py load usaspending-bulk --skip-download
        python main.py load usaspending-bulk --check-available
        python main.py load usaspending-bulk --check-available --fiscal-year 2026
    """
    logger = setup_logging()

    # --days-back mutual exclusivity
    if days_back is not None:
        if fiscal_year:
            raise click.UsageError("--days-back and --fiscal-year are mutually exclusive.")
        if years_back != 5:
            raise click.UsageError("--days-back and --years-back are mutually exclusive.")
        if delta:
            raise click.UsageError("--days-back and --delta are mutually exclusive.")
        if check_available:
            raise click.UsageError("--days-back and --check-available are mutually exclusive.")
        _run_days_back_load(logger, days_back, skip_download, fast)
        return

    # --check-available is incompatible with load-specific flags
    if check_available:
        if delta:
            raise click.UsageError("--check-available and --delta are mutually exclusive.")
        if skip_download:
            raise click.UsageError("--check-available and --skip-download are mutually exclusive.")
        if fast:
            raise click.UsageError("--check-available and --fast are mutually exclusive.")
        _check_available(fiscal_year, years_back)
        return

    # Mutual exclusivity: --delta cannot be combined with --fiscal-year or --years-back
    if delta and fiscal_year:
        raise click.UsageError("--delta and --fiscal-year are mutually exclusive.")
    if delta and years_back != 5:
        # years_back has default=5; only error if user explicitly passed it
        raise click.UsageError("--delta and --years-back are mutually exclusive.")

    from pathlib import Path
    from api_clients.usaspending_client import USASpendingClient
    from config import settings
    from etl.load_manager import LoadManager
    from etl.usaspending_bulk_loader import USASpendingBulkLoader

    if delta:
        _run_delta_load(logger, skip_download, fast)
        return

    # Determine fiscal years
    today = date.today()
    current_fy = today.year + 1 if today.month >= 10 else today.year

    if fiscal_year:
        fiscal_years = [fiscal_year]
    else:
        fiscal_years = list(range(current_fy - years_back + 1, current_fy + 1))

    click.echo(f"Fiscal years to load: {fiscal_years}")

    client = USASpendingClient()
    loader = USASpendingBulkLoader(fast_mode=fast)
    load_manager = LoadManager()
    download_dir = settings.DOWNLOAD_DIR / "usaspending"

    if fast:
        logger.warning(
            "Fast mode: secondary indexes will be dropped during load. "
            "Queries against usaspending_award will be slow until rebuild completes."
        )
        click.echo("WARNING: Fast mode enabled — secondary indexes will be dropped during load.")

    # Pre-load checks
    loader._check_buffer_pool_size()

    total_stats = {
        "records_read": 0,
        "records_inserted": 0,
        "records_errored": 0,
        "fiscal_years_loaded": 0,
    }

    if fast:
        loader._drop_secondary_indexes()
    else:
        # Crash recovery: rebuild indexes left dropped by a prior --fast crash
        rebuilt = loader._check_and_rebuild_indexes()
        if rebuilt:
            click.echo(f"  Rebuilt {rebuilt} missing secondary indexes from a prior crash.")

    try:
        for fy in fiscal_years:
            click.echo(f"\n--- FY{fy} ---")

            load_id = load_manager.start_load(
                source_system="USASPENDING_BULK",
                load_type="FULL",
                parameters={"fiscal_year": fy},
            )

            try:
                if skip_download:
                    # Find existing ZIP for this FY
                    zip_files = sorted(download_dir.glob(f"*{fy}*.zip")) if download_dir.exists() else []
                    if not zip_files:
                        click.echo(f"  No existing ZIP found for FY{fy}, skipping")
                        load_manager.fail_load(load_id, f"No ZIP file found for FY{fy}")
                        continue
                    zip_path = zip_files[-1]  # Most recent
                    click.echo(f"  Using existing: {zip_path.name}")
                else:
                    if source == "archive":
                        click.echo(f"  Downloading FY{fy} archive...")
                        zip_path = client.download_archive_file(fy)
                        click.echo(f"  Downloaded: {zip_path.name}")
                    else:
                        # On-demand API flow
                        click.echo(f"  Requesting bulk download for FY{fy}...")
                        result = client.request_bulk_download(fy)

                        if result.get("file_url"):
                            file_url = result["file_url"]
                        elif result.get("status_url"):
                            click.echo(f"  Polling for download readiness...")
                            poll_result = client.poll_bulk_download(result["status_url"])
                            file_url = poll_result["file_url"]
                        else:
                            raise RuntimeError(f"Unexpected API response: {result}")

                        click.echo(f"  Downloading...")
                        zip_path = client.download_bulk_file(file_url)

                # Load the ZIP
                click.echo(f"  Loading CSV data...")
                stats = loader.load_fiscal_year(zip_path, fy, load_id)

                load_manager.complete_load(
                    load_id,
                    records_read=stats["records_read"],
                    records_inserted=stats["records_inserted"],
                    records_errored=stats["records_errored"],
                )

                total_stats["records_read"] += stats["records_read"]
                total_stats["records_inserted"] += stats["records_inserted"]
                total_stats["records_errored"] += stats["records_errored"]
                total_stats["fiscal_years_loaded"] += 1

                click.echo(
                    f"  FY{fy}: {stats['records_read']:,} read, "
                    f"{stats['records_inserted']:,} upserted, "
                    f"{stats['records_errored']:,} errors"
                )

            except Exception as exc:
                logger.exception("Failed to load FY%d", fy)
                load_manager.fail_load(load_id, str(exc))
                click.echo(f"  FY{fy} FAILED: {exc}")

    finally:
        # Restore GLOBAL session settings changed during bulk load
        loader._restore_bulk_session_options()

        # Always rebuild indexes if --fast was used, regardless of how we exit
        # (success, exception, Ctrl+C / click.Abort)
        if fast:
            click.echo("Rebuilding secondary indexes...")
            loader._recreate_secondary_indexes()
            click.echo("Secondary indexes rebuilt.")

    click.echo(f"\n=== Summary ===")
    click.echo(f"Fiscal years loaded: {total_stats['fiscal_years_loaded']}")
    click.echo(f"Total records read:  {total_stats['records_read']:,}")
    click.echo(f"Total upserted:      {total_stats['records_inserted']:,}")
    click.echo(f"Total errors:        {total_stats['records_errored']:,}")


def _run_days_back_load(logger, days_back, skip_download, fast):
    """Load recent N days of USASpending data via the on-demand API."""
    from api_clients.usaspending_client import USASpendingClient
    from etl.load_manager import LoadManager
    from etl.usaspending_bulk_loader import USASpendingBulkLoader

    today = date.today()
    start_date = today - timedelta(days=days_back)
    end_date_str = today.strftime("%Y-%m-%d")
    start_date_str = start_date.strftime("%Y-%m-%d")

    # Use current FY as the fiscal_year label for the loader
    current_fy = today.year + 1 if today.month >= 10 else today.year

    click.echo(f"Loading {days_back} days of data: {start_date_str} to {end_date_str}")
    click.echo(f"  (Using on-demand API, fiscal year label: FY{current_fy})")

    client = USASpendingClient()
    loader = USASpendingBulkLoader(fast_mode=fast)
    load_manager = LoadManager()

    if fast:
        logger.warning(
            "Fast mode: secondary indexes will be dropped during load. "
            "Queries against usaspending_award will be slow until rebuild completes."
        )
        click.echo("WARNING: Fast mode enabled — secondary indexes will be dropped during load.")

    loader._check_buffer_pool_size()

    load_id = load_manager.start_load(
        source_system="USASPENDING_BULK",
        load_type="FULL",
        parameters={
            "days_back": days_back,
            "start_date": start_date_str,
            "end_date": end_date_str,
        },
    )

    if fast:
        loader._drop_secondary_indexes()
    else:
        rebuilt = loader._check_and_rebuild_indexes()
        if rebuilt:
            click.echo(f"  Rebuilt {rebuilt} missing secondary indexes from a prior crash.")

    try:
        if skip_download:
            raise click.UsageError(
                "--skip-download is not supported with --days-back "
                "(on-demand downloads have unique filenames)."
            )

        click.echo(f"  Requesting bulk download for {start_date_str} to {end_date_str}...")
        result = client.request_bulk_download(
            fiscal_year=current_fy,
            start_date=start_date_str,
            end_date=end_date_str,
        )

        if result.get("file_url"):
            file_url = result["file_url"]
        elif result.get("status_url"):
            click.echo(f"  Polling for download readiness...")
            poll_result = client.poll_bulk_download(result["status_url"])
            file_url = poll_result["file_url"]
        else:
            raise RuntimeError(f"Unexpected API response: {result}")

        click.echo(f"  Downloading...")
        zip_path = client.download_bulk_file(file_url)

        click.echo(f"  Loading CSV data...")
        stats = loader.load_fiscal_year(zip_path, current_fy, load_id)

        load_manager.complete_load(
            load_id,
            records_read=stats["records_read"],
            records_inserted=stats["records_inserted"],
            records_errored=stats["records_errored"],
        )

        click.echo(
            f"  {days_back}-day load: {stats['records_read']:,} read, "
            f"{stats['records_inserted']:,} upserted, "
            f"{stats['records_errored']:,} errors"
        )

    except click.UsageError:
        raise
    except Exception as exc:
        logger.exception("Failed to load %d-day range", days_back)
        load_manager.fail_load(load_id, str(exc))
        click.echo(f"  Days-back load FAILED: {exc}")

    finally:
        loader._restore_bulk_session_options()

        if fast:
            click.echo("Rebuilding secondary indexes...")
            loader._recreate_secondary_indexes()
            click.echo("Secondary indexes rebuilt.")


def _check_available(fiscal_year, years_back):
    """List available USASpending archive/delta files without downloading."""
    from api_clients.usaspending_client import USASpendingClient
    from db.connection import get_connection

    # Determine fiscal years (same logic as main command)
    today = date.today()
    current_fy = today.year + 1 if today.month >= 10 else today.year

    if fiscal_year:
        fiscal_years = [fiscal_year]
    else:
        fiscal_years = list(range(current_fy - years_back + 1, current_fy + 1))

    client = USASpendingClient()

    click.echo("USASpending Archive Availability (Contracts)\n")

    # Collect all files for hint comparison later
    all_available = []  # list of (fy, file_name, file_type, updated_date)

    for fy in fiscal_years:
        click.echo(f"FY{fy}:")
        try:
            data = client.list_archive_files(fy)
        except Exception as exc:
            click.echo(f"  Error querying FY{fy}: {exc}\n")
            continue

        monthly_files = data.get("monthly_files", [])
        if not monthly_files:
            click.echo("  No files available.\n")
            continue

        # Print header
        click.echo(f"  {'File Name':<52} {'Type':<8} {'Updated':<14} {'Size'}")

        for entry in monthly_files:
            file_name = entry.get("file_name", "")
            updated = entry.get("updated_date", "")
            file_size = entry.get("file_size")

            # Parse type from filename
            if "_Full_" in file_name:
                file_type = "Full"
            elif "_Delta_" in file_name:
                file_type = "Delta"
            else:
                file_type = "Other"

            # Format size
            if file_size:
                size_bytes = int(file_size)
                if size_bytes >= 1_073_741_824:
                    size_str = f"{size_bytes / 1_073_741_824:.1f} GB"
                elif size_bytes >= 1_048_576:
                    size_str = f"{size_bytes / 1_048_576:.0f} MB"
                elif size_bytes >= 1024:
                    size_str = f"{size_bytes / 1024:.0f} KB"
                else:
                    size_str = f"{size_bytes} B"
            else:
                size_str = "\u2014"

            # Prefix delta files for visibility
            type_label = f"[DELTA]" if file_type == "Delta" else file_type
            click.echo(f"  {file_name:<52} {type_label:<8} {updated:<14} {size_str}")

            all_available.append((fy, file_name, file_type, updated))

        click.echo()

    # Query last loaded info from etl_load_log
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT load_id, load_type, completed_at, records_inserted, parameters
            FROM etl_load_log
            WHERE source_system = 'USASPENDING_BULK'
              AND status = 'COMPLETE'
            ORDER BY completed_at DESC
        """)
        load_rows = cursor.fetchall()
        cursor.close()
        conn.close()
    except Exception as exc:
        click.echo(f"  (Could not query load history: {exc})\n")
        return

    if not load_rows:
        click.echo("Last loaded:\n  No completed loads found.\n")
        return

    # Organize loads: track last FULL per FY and last DELTA overall
    last_full_by_fy = {}  # fy -> row
    last_delta = None

    for row in load_rows:
        lt = row["load_type"]
        params = row.get("parameters")
        if isinstance(params, str):
            import json
            try:
                params = json.loads(params)
            except (json.JSONDecodeError, TypeError):
                params = {}
        elif params is None:
            params = {}

        if lt == "FULL":
            fy_val = params.get("fiscal_year")
            if fy_val and fy_val not in last_full_by_fy:
                last_full_by_fy[fy_val] = row
        elif lt == "DELTA" and last_delta is None:
            last_delta = row

    click.echo("Last loaded:")
    for fy in fiscal_years:
        if fy in last_full_by_fy:
            row = last_full_by_fy[fy]
            completed = row["completed_at"]
            completed_str = completed.strftime("%Y-%m-%d") if completed else "?"
            records = row.get("records_inserted", 0)
            click.echo(f"  Full  FY{fy}: {completed_str} (load #{row['load_id']}, {records:,} records)")
        else:
            click.echo(f"  Full  FY{fy}: (none)")

    if last_delta:
        completed = last_delta["completed_at"]
        completed_str = completed.strftime("%Y-%m-%d") if completed else "?"
        records = last_delta.get("records_inserted", 0)
        click.echo(f"  Delta:        {completed_str} (load #{last_delta['load_id']}, {records:,} records)")
    else:
        click.echo("  Delta:        (none)")

    click.echo()

    # Print hints: compare available files against last loaded dates
    for fy, file_name, file_type, updated in all_available:
        if not updated:
            continue

        if file_type == "Full" and fy in last_full_by_fy:
            last_completed = last_full_by_fy[fy]["completed_at"]
            if last_completed and updated > last_completed.strftime("%Y-%m-%d"):
                click.echo(
                    f"  \u2192 New FY{fy} full archive available ({updated}) "
                    f"since last load ({last_completed.strftime('%Y-%m-%d')})"
                )

        if file_type == "Delta" and last_delta:
            last_completed = last_delta["completed_at"]
            if last_completed and updated > last_completed.strftime("%Y-%m-%d"):
                click.echo(
                    f"  \u2192 New delta available ({updated}) "
                    f"since last load ({last_completed.strftime('%Y-%m-%d')})"
                )


def _run_delta_load(logger, skip_download, fast):
    """Download and load the latest USASpending monthly delta file."""
    from api_clients.usaspending_client import USASpendingClient
    from config import settings
    from etl.load_manager import LoadManager
    from etl.usaspending_bulk_loader import USASpendingBulkLoader

    client = USASpendingClient()
    loader = USASpendingBulkLoader(fast_mode=fast)
    load_manager = LoadManager()
    download_dir = settings.DOWNLOAD_DIR / "usaspending"

    if fast:
        logger.warning(
            "Fast mode: secondary indexes will be dropped during load. "
            "Queries against usaspending_award will be slow until rebuild completes."
        )
        click.echo("WARNING: Fast mode enabled — secondary indexes will be dropped during load.")

    loader._check_buffer_pool_size()

    load_id = load_manager.start_load(
        source_system="USASPENDING_BULK",
        load_type="DELTA",
        parameters={"delta": True},
    )

    if fast:
        loader._drop_secondary_indexes()
    else:
        rebuilt = loader._check_and_rebuild_indexes()
        if rebuilt:
            click.echo(f"  Rebuilt {rebuilt} missing secondary indexes from a prior crash.")

    try:
        if skip_download:
            # Find existing delta ZIP
            delta_zips = sorted(download_dir.glob("*Delta*.zip")) if download_dir.exists() else []
            if not delta_zips:
                raise RuntimeError("No existing delta ZIP found. Run without --skip-download first.")
            zip_path = delta_zips[-1]
            click.echo(f"  Using existing delta: {zip_path.name}")
        else:
            click.echo("  Downloading latest delta file...")
            zip_path = client.download_delta_file(download_dir)
            click.echo(f"  Downloaded: {zip_path.name}")

        click.echo("  Loading delta CSV data...")
        stats = loader.load_delta(zip_path, load_id=load_id)

        load_manager.complete_load(
            load_id,
            records_read=stats["records_read"],
            records_inserted=stats["records_inserted"],
            records_errored=stats["records_errored"],
        )

        click.echo(
            f"  Delta: {stats['records_read']:,} read, "
            f"{stats['records_inserted']:,} upserted, "
            f"{stats['records_deleted']:,} deleted, "
            f"{stats['records_errored']:,} errors"
        )

    except Exception as exc:
        logger.exception("Failed to load delta file")
        load_manager.fail_load(load_id, str(exc))
        click.echo(f"  Delta load FAILED: {exc}")

    finally:
        loader._restore_bulk_session_options()

        if fast:
            click.echo("Rebuilding secondary indexes...")
            loader._recreate_secondary_indexes()
            click.echo("Secondary indexes rebuilt.")
