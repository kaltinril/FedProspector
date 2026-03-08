"""CLI command for bulk loading USASpending award data (Phase 44A)."""

from datetime import date

import click

from config.logging_config import setup_logging


@click.command("usaspending-bulk")
@click.option("--years-back", default=5, type=int, help="Number of recent fiscal years to load")
@click.option("--fiscal-year", type=int, help="Load a single fiscal year (overrides --years-back)")
@click.option("--skip-download", is_flag=True, help="Use previously downloaded files")
@click.option("--source", type=click.Choice(["archive", "api"]), default="archive",
              help="Download source: archive (pre-built, fast) or api (on-demand, slow)")
@click.option("--fast", is_flag=True, default=False,
              help="Drop secondary indexes before load, rebuild after (faster bulk inserts)")
def usaspending_bulk(years_back, fiscal_year, skip_download, source, fast):
    """Bulk load USASpending award data from CSV downloads.

    Downloads fiscal-year bulk CSV archives from USASpending.gov and loads
    them into the usaspending_award table using LOAD DATA INFILE.

    Examples:
        python main.py load usaspending-bulk
        python main.py load usaspending-bulk --fiscal-year 2025
        python main.py load usaspending-bulk --years-back 3
        python main.py load usaspending-bulk --skip-download
    """
    logger = setup_logging()

    from pathlib import Path
    from api_clients.usaspending_client import USASpendingClient
    from config import settings
    from etl.load_manager import LoadManager
    from etl.usaspending_bulk_loader import USASpendingBulkLoader

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

    total_stats = {
        "records_read": 0,
        "records_inserted": 0,
        "records_errored": 0,
        "fiscal_years_loaded": 0,
    }

    if fast:
        loader._drop_secondary_indexes()

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
