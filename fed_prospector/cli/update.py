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
def fetch_descriptions(missing_only, batch_size):
    """Fetch and cache opportunity description text from SAM.gov.

    Queries opportunities with a description_url but no cached
    description_text, fetches the HTML description from SAM.gov's
    noticedesc endpoint, and stores it in the description_text column.

    Examples:
        python main.py update fetch-descriptions
        python main.py update fetch-descriptions --batch-size 50
        python main.py update fetch-descriptions --all
    """
    logger = setup_logging()

    from etl.opportunity_loader import OpportunityLoader

    loader = OpportunityLoader()
    mode = "missing only" if missing_only else "all"
    logger.info(
        "Starting description fetch (batch_size=%d, mode=%s)", batch_size, mode,
    )
    click.echo(f"Fetching descriptions ({mode}, batch_size={batch_size})...")

    stats = loader.fetch_descriptions(batch_size=batch_size, missing_only=missing_only)

    click.echo(
        f"Done. Found {stats['total_found']} opportunities, "
        f"fetched {stats['fetched']}, failed {stats['failed']}"
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
