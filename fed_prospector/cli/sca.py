"""SCA wage determination CLI commands.

Commands: load-sca, refresh-sca-list
"""

import sys

import click

from config.logging_config import setup_logging


@click.command("refresh-sca-list")
def refresh_sca_list():
    """Refresh the active SCA wage determination reference list.

    Downloads the active WD list from a saved SAM.gov search export,
    extracts WD numbers and revision numbers, and writes them to
    data/sca_active_wds.tsv for use by the loader.

    To update the source file:
      1. Open: https://sam.gov/search/?index=sca&page=1&pageSize=1100&sort=-modifiedDate&sfm%5Bstatus%5D%5Bis_active%5D=true
      2. Select all text on the page (Ctrl+A) and copy (Ctrl+C)
      3. Paste into a text file at: thesolution/reference/WD_YYYY-MM-DD.txt
      4. Run: python main.py update sca-list --file thesolution/reference/WD_YYYY-MM-DD.txt

    Examples:
        python main.py update sca-list --file thesolution/reference/WD_2026-04-04.txt
    """
    click.echo("Use: python main.py update sca-list --file <path>")
    click.echo("See --help for instructions on downloading the source file.")


@click.command("update-sca-list")
@click.option("--file", "input_file", required=True,
              help="Path to SAM.gov search export text file")
def update_sca_list(input_file):
    """Extract WD numbers + revisions from a SAM.gov search export.

    Parses a text file saved from the SAM.gov SCA search page and writes
    data/sca_active_wds.tsv with WD numbers and their current revisions.

    To get the source file:
      1. Open: https://sam.gov/search/?index=sca&page=1&pageSize=1100&sort=-modifiedDate&sfm%5Bstatus%5D%5Bis_active%5D=true
      2. Select all text (Ctrl+A), copy (Ctrl+C), paste into a .txt file

    Examples:
        python main.py update sca-list --file thesolution/reference/WD_2026-04-04.txt
    """
    import os
    import re

    with open(input_file, "r") as f:
        lines = f.readlines()

    pairs = []
    for i, line in enumerate(lines):
        m = re.search(r"Service Contract Act WD #:\s*(\S+)", line)
        if m:
            wd = m.group(1)
            for j in range(i + 1, min(i + 15, len(lines))):
                if lines[j].strip() == "Revision Number":
                    rev = lines[j + 1].strip() if j + 1 < len(lines) else ""
                    if rev.isdigit():
                        pairs.append((wd, int(rev)))
                    break

    if not pairs:
        click.echo("ERROR: No WD numbers found. Check the file format.")
        click.echo("Expected lines like: Service Contract Act WD #: 2015-4001")
        sys.exit(1)

    tsv_path = os.path.join(os.path.dirname(__file__), "..", "data", "sca_active_wds.tsv")
    tsv_path = os.path.normpath(tsv_path)

    with open(tsv_path, "w") as f:
        f.write("wd_number\trevision\n")
        for wd, rev in sorted(pairs):
            f.write(f"{wd}\t{rev}\n")

    click.echo(f"Wrote {len(pairs)} WD entries to {tsv_path}")
    click.echo(f"  WD range: {sorted(pairs)[0][0]} to {sorted(pairs)[-1][0]}")
    click.echo(f"  Revision range: {min(r for _, r in pairs)} to {max(r for _, r in pairs)}")
    click.echo("")
    click.echo("Now run: python main.py load sca")


@click.command("load-sca")
@click.option("--full-refresh", is_flag=True, help="Re-download all WDs instead of incremental")
@click.option("--wd-number", default=None, help="Load a single WD number (for testing)")
def load_sca(full_refresh, wd_number):
    """Load SCA wage determinations from SAM.gov.

    Downloads DOL wage determination text files from SAM.gov, parses the
    fixed-width format, and upserts into sca_wage_determination and
    sca_wage_rate tables.

    No API key required. No rate limiting (S3-backed).

    WD discovery sources (in priority order):
      1. Reference file (data/sca_active_wds.tsv) — has WD numbers + revisions,
         no probing needed. Refresh annually with: update sca-list --file <path>
      2. Database — uses existing WDs, checks each for new revisions via HEAD
         request. Good for monthly incremental checks.

    Examples:
        python main.py load sca                        # incremental
        python main.py load sca --full-refresh         # re-download everything
        python main.py load sca --wd-number 2015-4001  # single WD (testing)
    """
    import time
    logger = setup_logging()

    from api_clients.sca_wd_client import SCAWDClient
    from etl.sca_loader import SCALoader

    client = SCAWDClient()
    loader = SCALoader()

    click.echo("SCA Wage Determination Load")
    click.echo("  Data source: SAM.gov WD text files")
    click.echo("  Target: sca_wage_determination + sca_wage_rate (upsert)")
    if wd_number:
        click.echo("  Mode: SINGLE WD (%s)" % wd_number)
    else:
        click.echo("  Mode: %s" % ("FULL REFRESH" if full_refresh else "INCREMENTAL"))
    click.echo("")

    t_start = time.time()

    try:
        stats = loader.load(client, full_refresh=full_refresh, single_wd=wd_number)
        elapsed = time.time() - t_start

        click.echo("")
        click.echo("Load complete!")
        click.echo("  WDs processed:      %10d" % stats["wds_processed"])
        click.echo("  WDs inserted:       %10d" % stats["records_inserted"])
        click.echo("  WDs updated:        %10d" % stats["records_updated"])
        click.echo("  WDs unchanged:      %10d" % stats["records_unchanged"])
        click.echo("  WDs errored:        %10d" % stats["records_errored"])
        click.echo("  Rates inserted:     %10d" % stats["rates_inserted"])
        click.echo("  Rates updated:      %10d" % stats["rates_updated"])
        click.echo("  Time:               %10.1f seconds" % elapsed)

    except Exception as e:
        elapsed = time.time() - t_start
        logger.exception("SCA WD load failed")
        click.echo("\nERROR after %.1f seconds: %s" % (elapsed, e))
        sys.exit(1)
