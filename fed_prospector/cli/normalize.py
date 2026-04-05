"""Labor category normalization CLI commands.

Commands: labor-categories
"""

import sys

import click

from config.logging_config import setup_logging


_SOURCE_LABELS = {
    "gsa": ("GSA_CALC", "gsa_labor_rate.labor_category"),
    "sca": ("SCA", "sca_wage_rate.occupation_title"),
    "all": (None, "gsa_labor_rate + sca_wage_rate"),
}


@click.command("labor-categories")
@click.option("--seed-only", is_flag=True, help="Only seed canonical categories, skip normalization")
@click.option("--refresh-summary", is_flag=True, help="Only refresh the labor_rate_summary table")
@click.option(
    "--source", type=click.Choice(["gsa", "sca", "all"], case_sensitive=False),
    default="all", show_default=True,
    help="Which source to normalize: gsa (GSA CALC+), sca (SCA wage rates), or all",
)
def normalize_labor_categories(seed_only, refresh_summary, source):
    """Normalize labor categories to canonical categories.

    Multi-pass matching: exact, pattern (abbreviation expansion), and fuzzy
    (rapidfuzz token_sort_ratio >= 85). Maps raw labor category strings to
    ~200 canonical labor categories. Results stored in labor_category_mapping.

    Sources:
      gsa  - GSA CALC+ labor rate categories (~230K rows)
      sca  - DOL SCA occupation titles from wage determinations
      all  - Both GSA and SCA (default)

    After normalization, refreshes labor_rate_summary with aggregated
    statistics (count, min, avg, max, p25, median, p75) per canonical
    category, worksite, and education level.

    Examples:
        python main.py normalize labor-categories
        python main.py normalize labor-categories --source gsa
        python main.py normalize labor-categories --source sca
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

        # Determine which sources to normalize
        sources_to_run = []
        if source in ("gsa", "all"):
            sources_to_run.append("gsa")
        if source in ("sca", "all"):
            sources_to_run.append("sca")

        for src_key in sources_to_run:
            source_code, source_label = _SOURCE_LABELS[src_key]

            click.echo("Labor Category Normalization")
            click.echo("  Source: %s" % source_label)
            click.echo("  Target: labor_category_mapping (source=%s)" % source_code)
            click.echo("  Method: exact + pattern + fuzzy matching")
            click.echo("")

            if src_key == "gsa":
                stats = normalizer.normalize()
            else:
                stats = normalizer.normalize_sca()

            elapsed_src = time.time() - t_start

            click.echo("")
            click.echo("Normalization complete [%s]!" % source_code)
            click.echo("  Total categories:   %10d" % stats["total"])
            click.echo("  Exact matches:      %10d" % stats["exact"])
            click.echo("  Pattern matches:    %10d" % stats["pattern"])
            click.echo("  Fuzzy matches:      %10d" % stats["fuzzy"])
            click.echo("  Unmapped:           %10d" % stats["unmapped"])
            click.echo("  Time:               %10.1f seconds" % elapsed_src)
            click.echo("")

        # Auto-refresh summary after normalization
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
