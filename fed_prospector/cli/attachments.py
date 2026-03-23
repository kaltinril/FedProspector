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
@click.option("--delay", type=float, default=0.1, show_default=True,
              help="Delay in seconds between API requests")
@click.option("--active-only", is_flag=True, default=False,
              help="Only download for opportunities with future response deadlines")
@click.option("--workers", type=int, default=5, show_default=True,
              help="Number of concurrent download threads")
def download_attachments(notice_id, batch_size, max_file_size, missing_only,
                         check_changed, delay, active_only, workers):
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
    active_msg = ", active_only=True" if active_only else ""
    logger.info(
        "Starting attachment download (batch_size=%d, max_file_size=%dMB, delay=%.1fs%s)",
        batch_size, max_file_size, delay, active_msg,
    )
    click.echo(
        f"Downloading attachments (batch_size={batch_size}, "
        f"max_file_size={max_file_size}MB{active_msg})..."
    )

    stats = downloader.download_attachments(
        notice_id=notice_id,
        batch_size=batch_size,
        max_file_size_mb=max_file_size,
        missing_only=missing_only,
        check_changed=check_changed,
        delay=delay,
        active_only=active_only,
        workers=workers,
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
@click.option("--workers", type=int, default=10, show_default=True,
              help="Number of concurrent extraction threads")
def extract_attachment_text(notice_id, batch_size, force, workers):
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

    try:
        stats = extractor.extract_text(
            notice_id=notice_id,
            batch_size=batch_size,
            force=force,
            workers=workers,
        )
    except Exception as e:
        import threading
        logger.error(
            "Extraction crashed: %s (active threads: %d)",
            e, threading.active_count(),
        )
        raise

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


@click.command("pipeline-status")
def attachment_pipeline_status():
    """Show attachment intelligence pipeline status.

    Displays counts for each stage: downloads, text extraction,
    intel extraction, and file cleanup eligibility.

    Examples:
        python main.py health pipeline-status
    """
    setup_logging()

    from db.connection import get_connection
    import json

    conn = get_connection()
    cursor = conn.cursor()

    # Downloads
    cursor.execute("""
        SELECT download_status, COUNT(*)
        FROM opportunity_attachment
        GROUP BY download_status
        ORDER BY FIELD(download_status, 'downloaded', 'pending', 'failed', 'skipped')
    """)
    dl_rows = cursor.fetchall()
    dl_total = sum(r[1] for r in dl_rows)

    click.echo("=" * 55)
    click.echo("  Attachment Intelligence Pipeline Status")
    click.echo("=" * 55)
    click.echo()
    click.echo(f"  STAGE 1: Download ({dl_total:,} total)")
    for status, cnt in dl_rows:
        click.echo(f"    {status:<14} {cnt:>8,}")

    # Text extraction (of downloaded)
    cursor.execute("""
        SELECT extraction_status, COUNT(*)
        FROM opportunity_attachment
        WHERE download_status = 'downloaded'
        GROUP BY extraction_status
        ORDER BY FIELD(extraction_status, 'extracted', 'pending', 'failed', 'unsupported')
    """)
    ext_rows = cursor.fetchall()
    ext_total = sum(r[1] for r in ext_rows)

    click.echo()
    click.echo(f"  STAGE 2: Text Extraction ({ext_total:,} downloaded)")
    for status, cnt in ext_rows:
        click.echo(f"    {status:<14} {cnt:>8,}")

    # Intel extraction
    cursor.execute("""
        SELECT
            (SELECT COUNT(*) FROM opportunity_attachment WHERE extraction_status = 'extracted') as eligible,
            (SELECT COUNT(DISTINCT attachment_id) FROM opportunity_attachment_intel
             WHERE extraction_method IN ('keyword', 'heuristic')) as keyword_done,
            (SELECT COUNT(DISTINCT attachment_id) FROM opportunity_attachment_intel
             WHERE extraction_method IN ('ai_haiku', 'ai_sonnet')) as ai_done
    """)
    row = cursor.fetchone()
    eligible, keyword_done, ai_done = row

    click.echo()
    click.echo(f"  STAGE 3: Keyword Intel ({eligible:,} eligible)")
    click.echo(f"    completed       {keyword_done:>8,}")
    click.echo(f"    remaining       {eligible - keyword_done:>8,}")

    click.echo()
    click.echo(f"  STAGE 4: AI Analysis")
    click.echo(f"    completed       {ai_done:>8,}")
    click.echo(f"    remaining       {eligible - ai_done:>8,}")

    # Cleanup eligibility
    cursor.execute("""
        SELECT COUNT(*) FROM opportunity_attachment oa
        WHERE oa.download_status = 'downloaded'
          AND oa.extraction_status = 'extracted'
          AND oa.file_path IS NOT NULL
          AND EXISTS (
              SELECT 1 FROM opportunity_attachment_intel oai
              WHERE oai.attachment_id = oa.attachment_id
                AND oai.extraction_method IN ('keyword', 'heuristic')
          )
          AND EXISTS (
              SELECT 1 FROM opportunity_attachment_intel oai
              WHERE oai.attachment_id = oa.attachment_id
                AND oai.extraction_method IN ('ai_haiku', 'ai_sonnet')
          )
    """)
    cleanup_eligible = cursor.fetchone()[0]

    # Disk usage
    cursor.execute("""
        SELECT COALESCE(SUM(file_size_bytes), 0)
        FROM opportunity_attachment
        WHERE file_path IS NOT NULL AND download_status = 'downloaded'
    """)
    disk_bytes = cursor.fetchone()[0]

    # Filenames
    cursor.execute("""
        SELECT
            SUM(CASE WHEN filename IS NOT NULL
                      AND filename NOT LIKE 'Attachment%%'
                      AND filename NOT LIKE 'attachment%%'
                THEN 1 ELSE 0 END) as real_names,
            SUM(CASE WHEN filename IS NULL
                      OR filename LIKE 'Attachment%%'
                      OR filename LIKE 'attachment%%'
                THEN 1 ELSE 0 END) as generic_names
        FROM opportunity_attachment
    """)
    real_names, generic_names = cursor.fetchone()

    click.echo()
    click.echo(f"  STAGE 5: File Cleanup")
    click.echo(f"    eligible        {cleanup_eligible:>8,}")
    click.echo(f"    disk usage      {disk_bytes / (1024*1024*1024):>7.1f} GB")

    click.echo()
    click.echo(f"  Filenames")
    click.echo(f"    real names      {real_names:>8,}")
    click.echo(f"    generic/missing {generic_names:>8,}")

    click.echo()
    click.echo("=" * 55)

    cursor.close()
    conn.close()


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
