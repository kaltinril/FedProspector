"""CLI commands for data update/enrichment tasks."""

import click

from config.logging_config import setup_logging


@click.command("link-metadata")
@click.option("--missing-only", is_flag=True, default=True, show_default=True,
              help="Only process un-enriched resource links (default behavior)")
@click.option("--batch-size", type=int, default=100, show_default=True,
              help="Number of opportunities to process per batch")
def enrich_link_metadata(missing_only, batch_size):
    """Enrich opportunity resource links with filename and content-type metadata.

    HEAD-requests SAM.gov resource link URLs to extract filenames and
    content types, then updates the resource_links JSON column with
    enriched data (array of objects with url/filename/content_type).

    Examples:
        python main.py update link-metadata
        python main.py update link-metadata --batch-size 50
    """
    logger = setup_logging()

    from etl.opportunity_loader import OpportunityLoader

    loader = OpportunityLoader()
    logger.info("Starting resource link metadata enrichment (batch_size=%d)", batch_size)
    click.echo(f"Enriching resource link metadata (batch_size={batch_size})...")

    stats = loader.enrich_resource_links(batch_size=batch_size)

    click.echo(
        f"Done. Enriched {stats['opportunities_enriched']} opportunities "
        f"({stats['links_resolved']} links resolved)"
    )


@click.command("fetch-descriptions")
@click.option("--missing-only/--all", default=True, show_default=True,
              help="Only fetch for opportunities missing description_text")
@click.option("--batch-size", type=int, default=100, show_default=True,
              help="Number of opportunities to process per commit batch")
@click.option("--days-back", type=int, default=None,
              help="Only fetch descriptions for opportunities posted in the last N days")
@click.option("--notice-id", default=None,
              help="Fetch description for a single notice ID")
@click.option("--key", "api_key_number", default=2, type=click.IntRange(1, 2),
              help="Which SAM API key to use (1=free 10/day, 2=1000/day, default: 2)")
@click.option("--naics", default=None,
              help="Priority NAICS codes (comma-separated). Fetches these first, then others with remaining budget.")
@click.option("--set-aside", "set_aside", default=None,
              help="Priority set-aside codes (comma-separated, e.g. WOSB,8A,SBA). Fetches these first, then others with remaining budget.")
@click.option("--limit", type=int, default=None,
              help="Max total descriptions to fetch (default: unlimited)")
def fetch_descriptions(missing_only, batch_size, days_back, notice_id,
                       api_key_number, naics, set_aside, limit):
    """Fetch and cache opportunity description text from SAM.gov.

    Queries opportunities with a description_url but no cached
    description_text, fetches the HTML description from SAM.gov's
    noticedesc endpoint, and stores it in the description_text column.

    Each description requires one API call. Key 2 allows 1,000/day.

    When --naics and/or --set-aside are provided, performs a prioritized
    two-pass fetch: first fetches descriptions matching those filters,
    then uses remaining budget for all other opportunities.

    Examples:
        python main.py update fetch-descriptions --days-back 7
        python main.py update fetch-descriptions --notice-id abc123
        python main.py update fetch-descriptions --key 1 --notice-id abc123
        python main.py update fetch-descriptions --batch-size 900
        python main.py update fetch-descriptions --all
        python main.py update fetch-descriptions --naics 541511,541512 --set-aside WOSB,8A --limit 100
    """
    logger = setup_logging()

    from etl.opportunity_loader import OpportunityLoader

    loader = OpportunityLoader()
    mode = "missing only" if missing_only else "all"
    key_label = f"key {api_key_number}"

    naics_codes = [c.strip() for c in naics.split(",")] if naics else None
    set_aside_codes = [c.strip() for c in set_aside.split(",")] if set_aside else None

    if notice_id:
        click.echo(f"Fetching description for {notice_id} ({key_label})...")
    elif naics_codes or set_aside_codes:
        click.echo(f"Fetching descriptions (up to half for priority NAICS+set-aside, rest for all, limit={limit or 'unlimited'}, {key_label})...")
    elif days_back:
        click.echo(f"Fetching descriptions ({mode}, days_back={days_back}, {key_label})...")
    else:
        click.echo(f"Fetching descriptions ({mode}, batch_size={batch_size}, {key_label})...")

    stats = loader.fetch_descriptions(
        batch_size=batch_size,
        missing_only=missing_only,
        days_back=days_back,
        notice_id=notice_id,
        api_key_number=api_key_number,
        naics_codes=naics_codes,
        set_aside_codes=set_aside_codes,
        limit=limit,
    )

    click.echo(
        f"Done. Found {stats['total_found']} opportunities, "
        f"fetched {stats['fetched']}, failed {stats['failed']}"
    )
    if stats.get("priority_fetched"):
        click.echo(
            f"  Priority (NAICS+set-aside): {stats['priority_fetched']} fetched"
        )
        click.echo(
            f"  Remaining budget: {stats['fetched'] - stats['priority_fetched']} fetched"
        )


@click.command("build-relationships")
def build_relationships():
    """Detect and populate opportunity relationships from solicitation_number.

    Finds opportunities sharing the same solicitation_number and detects
    lifecycle progressions: RFI->RFP, PRESOL->SOL, SOL->AWARD.
    Uses INSERT IGNORE so it is safe to re-run.

    Examples:
        python main.py update build-relationships
    """
    logger = setup_logging()

    from etl.opportunity_loader import OpportunityLoader

    loader = OpportunityLoader()
    logger.info("Starting opportunity relationship detection")
    click.echo("Detecting opportunity relationships...")

    stats = loader.populate_relationships()

    click.echo(
        f"Done. Created {stats['total']} relationships: "
        f"RFI_TO_RFP={stats['RFI_TO_RFP']}, "
        f"PRESOL_TO_SOL={stats['PRESOL_TO_SOL']}, "
        f"SOL_TO_AWARD={stats['SOL_TO_AWARD']}"
    )
