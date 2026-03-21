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
