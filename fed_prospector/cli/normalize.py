"""Labor category normalization CLI commands.

Commands: labor-categories
"""

import sys

import click

from config.logging_config import setup_logging


@click.command("labor-categories")
@click.option("--seed-only", is_flag=True, help="Only seed canonical categories, skip normalization")
@click.option("--refresh-summary", is_flag=True, help="Only refresh the labor_rate_summary table")
def normalize_labor_categories(seed_only, refresh_summary):
    """Normalize GSA CALC+ labor categories to canonical categories.

    Multi-pass matching: exact, pattern (abbreviation expansion), and fuzzy
    (rapidfuzz token_sort_ratio >= 85). Maps ~230K gsa_labor_rate rows to
    ~200 canonical labor categories. Results stored in labor_category_mapping.

    After normalization, refreshes labor_rate_summary with aggregated
    statistics (count, min, avg, max, p25, median, p75) per canonical
    category, worksite, and education level.

    Examples:
        python main.py normalize labor-categories
        python main.py normalize labor-categories --seed-only
        python main.py normalize labor-categories --refresh-summary
    """
    import time
    logger = setup_logging()

    from etl.labor_normalizer import LaborNormalizer

    normalizer = LaborNormalizer()
    t_start = time.time()

    try:
        if seed_only:
            click.echo("Seeding canonical labor categories...")
            result = normalizer.seed_canonical_categories()
            elapsed = time.time() - t_start
            click.echo("")
            click.echo("Seed complete!")
            click.echo("  Categories read:    %10d" % result["rows_read"])
            click.echo("  Rows affected:      %10d" % result["rows_affected"])
            click.echo("  Time:               %10.1f seconds" % elapsed)
            return

        if refresh_summary:
            click.echo("Refreshing labor rate summary...")
            result = normalizer.refresh_summary()
            elapsed = time.time() - t_start
            click.echo("")
            click.echo("Summary refresh complete!")
            click.echo("  Summary rows:       %10d" % result["summary_rows"])
            click.echo("  Time:               %10.1f seconds" % elapsed)
            return

        # Full normalization
        click.echo("Labor Category Normalization")
        click.echo("  Source: gsa_labor_rate.labor_category")
        click.echo("  Target: labor_category_mapping -> canonical_labor_category")
        click.echo("  Method: exact + pattern + fuzzy matching")
        click.echo("")

        stats = normalizer.normalize()
        elapsed_norm = time.time() - t_start

        click.echo("")
        click.echo("Normalization complete!")
        click.echo("  Total categories:   %10d" % stats["total"])
        click.echo("  Exact matches:      %10d" % stats["exact"])
        click.echo("  Pattern matches:    %10d" % stats["pattern"])
        click.echo("  Fuzzy matches:      %10d" % stats["fuzzy"])
        click.echo("  Unmapped:           %10d" % stats["unmapped"])
        click.echo("  Time:               %10.1f seconds" % elapsed_norm)

        # Auto-refresh summary after normalization
        click.echo("")
        click.echo("Refreshing labor rate summary...")
        summary_result = normalizer.refresh_summary()
        elapsed_total = time.time() - t_start

        click.echo("  Summary rows:       %10d" % summary_result["summary_rows"])
        click.echo("  Total time:         %10.1f seconds" % elapsed_total)

    except Exception as e:
        elapsed = time.time() - t_start
        logger.exception("Labor normalization failed")
        click.echo("\nERROR after %.1f seconds: %s" % (elapsed, e))
        sys.exit(1)
