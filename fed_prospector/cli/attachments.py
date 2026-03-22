"""CLI commands for the attachment intelligence pipeline (Phase 110)."""

import click

from config.logging_config import setup_logging


@click.command("attachments")
@click.option("--notice-id", type=str, default=None,
              help="Process a single opportunity by notice ID")
@click.option("--batch-size", type=int, default=100, show_default=True,
              help="Number of attachments to process per batch")
@click.option("--max-file-size", type=int, default=50, show_default=True,
              help="Maximum file size in MB to download")
@click.option("--missing-only", is_flag=True, default=False,
              help="Only download attachments not yet stored locally")
@click.option("--check-changed", is_flag=True, default=False,
              help="Re-download if remote file has changed (hash check)")
@click.option("--delay", type=float, default=0.5, show_default=True,
              help="Delay in seconds between API requests")
def download_attachments(notice_id, batch_size, max_file_size, missing_only,
                         check_changed, delay):
    """Download opportunity attachments from SAM.gov.

    Fetches attachment files (PDFs, DOCXs, etc.) for opportunities that
    have resource links, and stores them locally for text extraction.

    Examples:
        python main.py download attachments
        python main.py download attachments --notice-id abc123
        python main.py download attachments --missing-only --batch-size 50
    """
    logger = setup_logging()

    from etl.attachment_downloader import AttachmentDownloader

    downloader = AttachmentDownloader()
    logger.info(
        "Starting attachment download (batch_size=%d, max_file_size=%dMB, delay=%.1fs)",
        batch_size, max_file_size, delay,
    )
    click.echo(
        f"Downloading attachments (batch_size={batch_size}, "
        f"max_file_size={max_file_size}MB)..."
    )

    stats = downloader.download_attachments(
        notice_id=notice_id,
        batch_size=batch_size,
        max_file_size_mb=max_file_size,
        missing_only=missing_only,
        check_changed=check_changed,
        delay=delay,
    )

    click.echo(
        f"Done. Downloaded {stats.get('downloaded', 0)} attachments, "
        f"skipped {stats.get('skipped', 0)}, "
        f"failed {stats.get('failed', 0)}"
    )


@click.command("attachment-text")
@click.option("--notice-id", type=str, default=None,
              help="Process a single opportunity by notice ID")
@click.option("--batch-size", type=int, default=100, show_default=True,
              help="Number of attachments to process per batch")
@click.option("--force", is_flag=True, default=False,
              help="Re-extract text even if already extracted")
def extract_attachment_text(notice_id, batch_size, force):
    """Extract text content from downloaded attachments.

    Parses PDF, DOCX, and other document formats to extract raw text
    for downstream intelligence extraction.

    Examples:
        python main.py extract attachment-text
        python main.py extract attachment-text --notice-id abc123
        python main.py extract attachment-text --force --batch-size 50
    """
    logger = setup_logging()

    from etl.attachment_text_extractor import AttachmentTextExtractor

    extractor = AttachmentTextExtractor()
    logger.info(
        "Starting attachment text extraction (batch_size=%d, force=%s)",
        batch_size, force,
    )
    click.echo(f"Extracting text from attachments (batch_size={batch_size})...")

    stats = extractor.extract_text(
        notice_id=notice_id,
        batch_size=batch_size,
        force=force,
    )

    click.echo(
        f"Done. Extracted {stats.get('extracted', 0)} attachments, "
        f"skipped {stats.get('skipped', 0)}, "
        f"failed {stats.get('failed', 0)}"
    )


@click.command("attachment-intel")
@click.option("--notice-id", type=str, default=None,
              help="Process a single opportunity by notice ID")
@click.option("--batch-size", type=int, default=100, show_default=True,
              help="Number of attachments to process per batch")
@click.option("--method", type=click.Choice(["keyword", "regex", "hybrid"]),
              default="keyword", show_default=True,
              help="Intelligence extraction method")
@click.option("--force", is_flag=True, default=False,
              help="Re-extract intel even if already extracted")
def extract_attachment_intel(notice_id, batch_size, method, force):
    """Extract structured intelligence from attachment text.

    Parses extracted text to identify key requirements, evaluation
    criteria, set-aside details, and other bid-relevant information
    using keyword or regex-based extraction.

    Examples:
        python main.py extract attachment-intel
        python main.py extract attachment-intel --method regex
        python main.py extract attachment-intel --notice-id abc123 --force
    """
    logger = setup_logging()

    from etl.attachment_intel_extractor import AttachmentIntelExtractor

    extractor = AttachmentIntelExtractor()
    logger.info(
        "Starting attachment intel extraction (batch_size=%d, method=%s, force=%s)",
        batch_size, method, force,
    )
    click.echo(
        f"Extracting intelligence from attachments "
        f"(batch_size={batch_size}, method={method})..."
    )

    stats = extractor.extract_intel(
        notice_id=notice_id,
        batch_size=batch_size,
        method=method,
        force=force,
    )

    click.echo(
        f"Done. Processed {stats.get('processed', 0)} attachments, "
        f"extracted {stats.get('extracted', 0)} intel records, "
        f"failed {stats.get('failed', 0)}"
    )


@click.command("attachments")
@click.option("--notice-id", type=str, default=None,
              help="Process a single opportunity by notice ID")
@click.option("--batch-size", type=int, default=50, show_default=True,
              help="Number of attachments to process per batch")
@click.option("--model", type=click.Choice(["haiku", "sonnet", "opus"]),
              default="haiku", show_default=True,
              help="Claude model to use for analysis")
@click.option("--force", is_flag=True, default=False,
              help="Re-analyze even if already analyzed")
def analyze_attachments(notice_id, batch_size, model, force):
    """Analyze attachment content using Claude AI.

    Uses Claude to perform deep analysis of attachment text, extracting
    nuanced requirements and competitive intelligence. (Phase 110 Round 3)

    Examples:
        python main.py analyze attachments
        python main.py analyze attachments --model sonnet
        python main.py analyze attachments --notice-id abc123
    """
    setup_logging()
    click.echo("AI analysis not yet implemented (Phase 110 Round 3)")


@click.command("attachment-files")
@click.option("--notice-id", type=str, default=None,
              help="Only clean up files for this notice ID")
@click.option("--batch-size", type=int, default=1000, show_default=True,
              help="Maximum number of files to process")
@click.option("--dry-run", is_flag=True, default=False,
              help="Show what would be deleted without actually deleting")
def cleanup_attachment_files(notice_id, batch_size, dry_run):
    """Remove attachment files that completed the full analysis pipeline.

    Only deletes files that passed through ALL 4 stages:

      1. Downloaded (file on disk)
      2. Text extracted (text stored in DB)
      3. Keyword/heuristic intel extracted
      4. AI analysis complete (Claude Haiku/Sonnet)

    All extracted data remains in the database — only the original
    files are removed. Use --dry-run first to preview.

    Examples:
        python main.py cleanup attachment-files --dry-run
        python main.py cleanup attachment-files
        python main.py cleanup attachment-files --notice-id abc123
    """
    logger = setup_logging()

    from etl.attachment_cleanup import AttachmentFileCleanup

    cleanup = AttachmentFileCleanup()

    if dry_run:
        click.echo("DRY RUN — no files will be deleted")

    click.echo(f"Scanning for fully-analyzed attachment files (batch_size={batch_size})...")

    stats = cleanup.cleanup_files(
        notice_id=notice_id,
        batch_size=batch_size,
        dry_run=dry_run,
    )

    size_mb = stats["bytes_reclaimed"] / (1024 * 1024)
    verb = "Would delete" if dry_run else "Deleted"
    parts = [
        f"Done. {verb} {stats['deleted']} of {stats['eligible']} eligible files "
        f"({size_mb:.1f} MB {'reclaimable' if dry_run else 'reclaimed'})",
    ]
    if stats.get("already_missing"):
        parts.append(f"{stats['already_missing']} already missing from disk")
    if stats["failed"]:
        parts.append(f"{stats['failed']} failed")
    click.echo(", ".join(parts))
