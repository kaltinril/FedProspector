"""Entity data CLI commands.

Commands: download-extract, load-entities, refresh-entities
"""

import sys
from pathlib import Path

import click

from config.logging_config import setup_logging
from config import settings


@click.command("download-extract")
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


@click.command("refresh-entities")
@click.option("--type", "extract_type", type=click.Choice(["daily", "monthly"]),
              default="daily", help="Extract type: daily (incremental) or monthly (full)")
@click.option("--year", type=int, default=None,
              help="Year for monthly extract (default: current year)")
@click.option("--month", type=int, default=None,
              help="Month for monthly extract (default: current month)")
@click.option("--date", "extract_date", default=None,
              help="Date for daily extract (YYYY-MM-DD, default: today)")
@click.option("--batch-size", default=1000, type=int,
              help="Records per batch commit for JSON mode (default: 1000)")
def refresh_entities(extract_type, year, month, extract_date, batch_size):
    """Download and load SAM.gov entity extract in a single step.

    Combines download-extract and load-entities into one command.
    Downloads the extract, then loads each extracted file automatically.

    Examples:
        python main.py refresh-entities --type=daily
        python main.py refresh-entities --type=daily --date=2026-02-21
        python main.py refresh-entities --type=monthly --year=2026 --month=2
    """
    logger = setup_logging()
    from datetime import date as date_cls
    from api_clients.sam_extract_client import SAMExtractClient

    if not settings.SAM_API_KEY or settings.SAM_API_KEY == "your_api_key_here":
        click.echo("ERROR: SAM_API_KEY not configured in .env file")
        sys.exit(1)

    client = SAMExtractClient()

    # ---- Step 1: Download ----
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
        except Exception as e:
            click.echo(f"ERROR during download: {e}")
            sys.exit(1)
        mode = "full"

    else:  # daily
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
        except Exception as e:
            click.echo(f"ERROR during download: {e}")
            sys.exit(1)
        mode = "daily"

    # ---- Step 2: Load each extracted file ----
    click.echo(f"\nLoading {len(paths)} file(s)...")

    for fp in paths:
        fp = Path(fp)
        file_ext = fp.suffix.lower()

        if file_ext == ".dat":
            # ---- DAT file: use bulk loader (LOAD DATA INFILE) ----
            from etl.dat_parser import parse_dat_file, get_dat_record_count
            from etl.bulk_loader import BulkLoader

            try:
                record_count = get_dat_record_count(str(fp))
                click.echo(f"\nLoading DAT file: {fp.name}")
                click.echo(f"  Records in file (from header): {record_count:,d}")
                click.echo(f"  Method: LOAD DATA INFILE (bulk)")
                click.echo(f"  Mode: {mode}")
            except ValueError as e:
                click.echo(f"WARNING: Could not read DAT header: {e}")
                click.echo(f"\nLoading DAT file: {fp.name}")

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

            click.echo(f"\nLoading JSON file: {fp.name}")
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

    click.echo(f"\nRefresh complete! ({len(paths)} file(s) processed)")
