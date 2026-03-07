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
