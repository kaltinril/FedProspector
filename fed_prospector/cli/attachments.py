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
@click.option("--delay", type=float, default=0.05, show_default=True,
              help="Delay in seconds between API requests")
@click.option("--active-only", is_flag=True, default=False,
              help="Only download for opportunities with future response deadlines")
@click.option("--workers", type=int, default=10, show_default=True,
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
        "Starting attachment download (batch_size=%d, max_file_size=%dMB, delay=%gs%s)",
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
@click.option("--timeout", type=int, default=120, show_default=True,
              help="Per-file extraction timeout in seconds")
@click.option("--reset-retries", type=str, default=None,
              help="Comma-separated document IDs to reset extraction_retry_count to 0, "
                   "then exit without running extraction.")
@click.option("--reset-all-retries", is_flag=True, default=False,
              help="Reset extraction_retry_count to 0 for ALL documents that hit the "
                   "10-retry cap, then exit without running extraction.")
def extract_attachment_text(notice_id, batch_size, force, workers, timeout,
                            reset_retries, reset_all_retries):
    """Extract text content from downloaded attachments.

    Parses PDF, DOCX, and other document formats to extract raw text
    for downstream intelligence extraction.

    Examples:
        python main.py extract attachment-text
        python main.py extract attachment-text --notice-id abc123
        python main.py extract attachment-text --force --batch-size 50
        python main.py extract attachment-text --reset-retries 123,456,789
        python main.py extract attachment-text --reset-all-retries
    """
    logger = setup_logging()

    if reset_retries or reset_all_retries:
        from db.connection import get_connection
        conn = get_connection()
        cursor = conn.cursor()
        try:
            if reset_all_retries:
                cursor.execute(
                    "UPDATE attachment_document SET extraction_retry_count = 0 "
                    "WHERE extraction_retry_count >= 10"
                )
            else:
                ids = [int(x.strip()) for x in reset_retries.split(",") if x.strip()]
                if not ids:
                    click.echo("Error: --reset-retries requires at least one document ID", err=True)
                    raise SystemExit(1)
                placeholders = ",".join(["%s"] * len(ids))
                cursor.execute(
                    f"UPDATE attachment_document SET extraction_retry_count = 0 "
                    f"WHERE document_id IN ({placeholders})",
                    ids,
                )
            conn.commit()
            click.echo(f"Reset extraction_retry_count for {cursor.rowcount} document(s).")
            logger.info("Reset extraction_retry_count for %d document(s)", cursor.rowcount)
        finally:
            cursor.close()
            conn.close()
        return

    from etl.attachment_text_extractor import AttachmentTextExtractor

    extractor = AttachmentTextExtractor()
    logger.info(
        "Starting attachment text extraction (batch_size=%d, force=%s, timeout=%ds)",
        batch_size, force, timeout,
    )
    click.echo(f"Extracting text from attachments (batch_size={batch_size})...")

    try:
        stats = extractor.extract_text(
            notice_id=notice_id,
            batch_size=batch_size,
            force=force,
            workers=workers,
            timeout_seconds=timeout,
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
        f"failed {stats.get('failed', 0)}, "
        f"timeout {stats.get('timeout', 0)}"
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
@click.option("--dump", is_flag=True, default=False,
              help="Dump intel dict to JSON file on DB insert error and stop")
@click.option("--workers", type=int, default=4, show_default=True,
              help="Number of parallel worker processes (1 = serial, for debugging)")
def extract_attachment_intel(notice_id, batch_size, method, force, dump, workers):
    """Extract structured intelligence from attachment text.

    Parses extracted text to identify key requirements, evaluation
    criteria, set-aside details, and other bid-relevant information
    using keyword or regex-based extraction.

    Examples:
        python main.py extract attachment-intel
        python main.py extract attachment-intel --method regex
        python main.py extract attachment-intel --notice-id abc123 --force
        python main.py extract attachment-intel --workers 1   # serial, for debugging
    """
    logger = setup_logging()

    from etl.attachment_intel_extractor import AttachmentIntelExtractor

    extractor = AttachmentIntelExtractor(dump_on_error=dump)
    logger.info(
        "Starting attachment intel extraction (batch_size=%d, method=%s, force=%s, workers=%d)",
        batch_size, method, force, workers,
    )
    click.echo(
        f"Extracting intelligence from attachments "
        f"(batch_size={batch_size}, method={method}, workers={workers})..."
    )

    stats = extractor.extract_intel(
        notice_id=notice_id,
        batch_size=batch_size,
        method=method,
        force=force,
        workers=workers,
    )

    click.echo(
        f"Done. Processed {stats.get('notices_processed', 0)} notices, "
        f"extracted {stats.get('intel_rows_upserted', 0)} intel records, "
        f"{stats.get('source_rows_inserted', 0)} evidence rows"
    )


@click.command("description-intel")
@click.option("--notice-id", type=str, default=None,
              help="Process a single opportunity by notice ID")
@click.option("--batch-size", type=int, default=500, show_default=True,
              help="Number of notices to process per batch")
@click.option("--force", is_flag=True, default=False,
              help="Re-extract intel even if already extracted")
@click.option("--workers", type=int, default=4, show_default=True,
              help="Number of parallel worker processes (1 = serial, for debugging)")
def extract_description_intel(notice_id, batch_size, force, workers):
    """Extract structured intelligence from opportunity description text.

    Runs keyword/regex patterns against opportunity description_text to
    extract clearance requirements, evaluation criteria, vehicle type,
    recompete signals, and other bid-relevant intelligence.

    Only processes opportunities with description_text. Does not touch
    attachment documents. Results stored separately from attachment intel
    using extraction_method='description_keyword'.

    Examples:
        python main.py extract description-intel
        python main.py extract description-intel --notice-id abc123
        python main.py extract description-intel --batch-size 1000 --force
    """
    logger = setup_logging()

    from etl.attachment_intel_extractor import AttachmentIntelExtractor

    extractor = AttachmentIntelExtractor()
    logger.info(
        "Starting description intel extraction (batch_size=%d, force=%s, workers=%d)",
        batch_size, force, workers,
    )
    click.echo(
        f"Extracting intelligence from descriptions "
        f"(batch_size={batch_size}, workers={workers})..."
    )

    stats = extractor.extract_intel(
        notice_id=notice_id,
        batch_size=batch_size,
        method="description_keyword",
        force=force,
        description_only=True,
        workers=workers,
    )

    click.echo(
        f"Done. Processed {stats.get('notices_processed', 0)} notices, "
        f"extracted {stats.get('intel_rows_upserted', 0)} intel records"
    )


@click.command("attachments")
@click.option("--notice-id", type=str, default=None,
              help="Process a single opportunity by notice ID")
@click.option("--batch-size", type=int, default=50, show_default=True,
              help="Number of attachments to process per batch")
@click.option("--model", type=click.Choice(["haiku", "sonnet"]),
              # opus excluded — add 'ai_opus' to extraction_method ENUM in 36_attachment.sql before enabling
              default="haiku", show_default=True,
              help="Claude model to use for analysis")
@click.option("--force", is_flag=True, default=False,
              help="Re-analyze even if already analyzed")
@click.option("--dry-run", is_flag=True, default=False,
              help="Run full pipeline without calling the API (no ANTHROPIC_API_KEY needed)")
def analyze_attachments(notice_id, batch_size, model, force, dry_run):
    """Analyze attachment content using Claude AI.

    Sends extracted document text to Claude for structured analysis,
    extracting clearance requirements, evaluation criteria, contract
    vehicle info, incumbent details, and more.

    Use --dry-run to test the full pipeline without an API key.

    Examples:
        python main.py extract attachment-ai
        python main.py extract attachment-ai --model sonnet
        python main.py extract attachment-ai --notice-id abc123
        python main.py extract attachment-ai --dry-run
    """
    logger = setup_logging()

    from etl.attachment_ai_analyzer import AttachmentAIAnalyzer

    if dry_run:
        click.echo("DRY RUN — no API calls will be made, mock results will be saved with method 'ai_dry_run'")

    analyzer = AttachmentAIAnalyzer(model=model, dry_run=dry_run)

    logger.info(
        "Starting AI analysis (model=%s, batch_size=%d, force=%s, dry_run=%s)",
        model, batch_size, force, dry_run,
    )
    click.echo(
        f"Analyzing attachments with Claude {model} "
        f"(batch_size={batch_size}{', dry_run' if dry_run else ''})..."
    )

    try:
        stats = analyzer.analyze(
            notice_id=notice_id,
            batch_size=batch_size,
            force=force,
        )
    except RuntimeError as e:
        # Missing API key
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    click.echo(
        f"Done. Analyzed {stats['analyzed']} documents, "
        f"skipped {stats['skipped']}, "
        f"failed {stats['failed']}"
    )


@click.command("descriptions")
@click.option("--notice-id", type=str, default=None,
              help="Process a single opportunity by notice ID")
@click.option("--batch-size", type=int, default=50, show_default=True,
              help="Number of notices to process per batch")
@click.option("--model", type=click.Choice(["haiku", "sonnet"]),
              # opus excluded — add 'ai_opus' to extraction_method ENUM in 36_attachment.sql before enabling
              default="haiku", show_default=True,
              help="Claude model to use for analysis")
@click.option("--force", is_flag=True, default=False,
              help="Re-analyze even if already analyzed")
@click.option("--dry-run", is_flag=True, default=False,
              help="Run full pipeline without calling the API (no ANTHROPIC_API_KEY needed)")
def analyze_descriptions(notice_id, batch_size, model, force, dry_run):
    """Analyze opportunity description text using Claude AI (Phase 121).

    Sends opportunity description_text (and any available attachment text)
    to Claude for structured intelligence extraction. Results are stored
    in opportunity_attachment_summary as AI-method rows.

    Useful for opportunities that have descriptions but no downloadable
    attachments, or to enhance attachment-based intel with description context.

    Use --dry-run to test the full pipeline without an API key.

    Examples:
        python main.py extract description-ai
        python main.py extract description-ai --model sonnet
        python main.py extract description-ai --notice-id abc123
        python main.py extract description-ai --dry-run
    """
    logger = setup_logging()

    from etl.attachment_ai_analyzer import AttachmentAIAnalyzer

    if dry_run:
        click.echo("DRY RUN — no API calls will be made, mock results will be saved with method 'ai_dry_run'")

    analyzer = AttachmentAIAnalyzer(model=model, dry_run=dry_run)

    logger.info(
        "Starting description AI analysis (model=%s, batch_size=%d, force=%s, dry_run=%s)",
        model, batch_size, force, dry_run,
    )
    click.echo(
        f"Analyzing descriptions with Claude {model} "
        f"(batch_size={batch_size}{', dry_run' if dry_run else ''})..."
    )

    try:
        stats = analyzer.analyze_descriptions(
            notice_id=notice_id,
            batch_size=batch_size,
            force=force,
        )
    except RuntimeError as e:
        # Missing API key
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    click.echo(
        f"Done. Analyzed {stats['analyzed']} descriptions, "
        f"skipped {stats['skipped']}, "
        f"failed {stats['failed']}"
    )


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

    # Map table count (opportunity_attachment is now a lean join table)
    cursor.execute("SELECT COUNT(*) FROM opportunity_attachment")
    map_total = cursor.fetchone()[0]

    # Downloads (from sam_attachment)
    cursor.execute("""
        SELECT download_status, COUNT(*)
        FROM sam_attachment
        GROUP BY download_status
        ORDER BY FIELD(download_status, 'downloaded', 'pending', 'failed', 'skipped')
    """)
    dl_rows = cursor.fetchall()
    dl_total = sum(r[1] for r in dl_rows)

    click.echo("=" * 55)
    click.echo("  Attachment Intelligence Pipeline Status")
    click.echo("=" * 55)
    click.echo()
    click.echo(f"  STAGE 1: Download ({dl_total:,} unique files, {map_total:,} map rows)")
    for status, cnt in dl_rows:
        click.echo(f"    {status:<14} {cnt:>8,}")

    # Text extraction (from attachment_document, joined to downloaded sam_attachment)
    cursor.execute("""
        SELECT ad.extraction_status, COUNT(*)
        FROM attachment_document ad
        JOIN sam_attachment sa ON sa.attachment_id = ad.attachment_id
        WHERE sa.download_status = 'downloaded'
        GROUP BY ad.extraction_status
        ORDER BY FIELD(ad.extraction_status, 'extracted', 'pending', 'failed', 'unsupported')
    """)
    ext_rows = cursor.fetchall()
    ext_total = sum(r[1] for r in ext_rows)

    click.echo()
    click.echo(f"  STAGE 2: Text Extraction ({ext_total:,} downloaded)")
    for status, cnt in ext_rows:
        click.echo(f"    {status:<14} {cnt:>8,}")

    # Intel extraction status — use attachment_document.{keyword,ai}_analyzed_at
    # rather than document_intel_summary, because the extractors only insert a
    # summary row when they FIND something. A doc that's been analyzed but
    # produced zero findings (e.g. blank templates, scanned maps, wage decisions)
    # has its analyzed_at timestamp set but no summary row — it should count as
    # "done", not "remaining".
    cursor.execute("""
        SELECT
            (SELECT COUNT(*) FROM attachment_document
             WHERE extraction_status = 'extracted') as eligible,
            (SELECT COUNT(*) FROM attachment_document
             WHERE extraction_status = 'extracted'
               AND keyword_analyzed_at IS NOT NULL) as keyword_done,
            (SELECT COUNT(*) FROM attachment_document
             WHERE extraction_status = 'extracted'
               AND ai_analyzed_at IS NOT NULL) as ai_done
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

    # Cleanup eligibility (join sam_attachment -> attachment_document -> document_intel_summary)
    cursor.execute("""
        SELECT COUNT(*) FROM sam_attachment sa
        WHERE sa.download_status = 'downloaded'
          AND sa.file_path IS NOT NULL
          AND EXISTS (
              SELECT 1 FROM attachment_document ad
              WHERE ad.attachment_id = sa.attachment_id
                AND ad.extraction_status = 'extracted'
          )
          AND EXISTS (
              SELECT 1 FROM attachment_document ad
              JOIN document_intel_summary dis ON dis.document_id = ad.document_id
              WHERE ad.attachment_id = sa.attachment_id
                AND dis.extraction_method IN ('keyword', 'heuristic')
          )
          AND EXISTS (
              SELECT 1 FROM attachment_document ad
              JOIN document_intel_summary dis ON dis.document_id = ad.document_id
              WHERE ad.attachment_id = sa.attachment_id
                AND dis.extraction_method IN ('ai_haiku', 'ai_sonnet')
          )
    """)
    cleanup_eligible = cursor.fetchone()[0]

    # Disk usage (from sam_attachment)
    cursor.execute("""
        SELECT COALESCE(SUM(file_size_bytes), 0)
        FROM sam_attachment
        WHERE file_path IS NOT NULL AND download_status = 'downloaded'
    """)
    disk_bytes = cursor.fetchone()[0]

    # Filenames (from sam_attachment)
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
        FROM sam_attachment
    """)
    real_names, generic_names = cursor.fetchone()

    # Description intel (Phase 121)
    cursor.execute("""
        SELECT
            (SELECT COUNT(*) FROM opportunity
             WHERE description_text IS NOT NULL AND description_text != '') as desc_total,
            (SELECT COUNT(DISTINCT notice_id) FROM opportunity_attachment_summary
             WHERE extraction_method IN ('keyword', 'heuristic')) as desc_keyword_done,
            (SELECT COUNT(DISTINCT notice_id) FROM opportunity_attachment_summary
             WHERE extraction_method IN ('ai_haiku', 'ai_sonnet')) as desc_ai_done
    """)
    desc_row = cursor.fetchone()
    desc_total, desc_keyword_done, desc_ai_done = desc_row

    click.echo()
    click.echo(f"  STAGE 4B: Description Intel ({desc_total:,} with descriptions)")
    click.echo(f"    keyword done    {desc_keyword_done:>8,}")
    click.echo(f"    AI done         {desc_ai_done:>8,}")
    click.echo(f"    AI remaining    {desc_total - desc_ai_done:>8,}")

    click.echo()
    click.echo(f"  STAGE 5: File Cleanup")
    click.echo(f"    eligible        {cleanup_eligible:>8,}")
    click.echo(f"    disk usage      {disk_bytes / (1024*1024*1024):>7.1f} GB")

    click.echo()
    click.echo(f"  Filenames")
    click.echo(f"    real names      {real_names:>8,}")
    click.echo(f"    generic/missing {generic_names:>8,}")

    # Deduplication (Phase 124)
    cursor.execute("""
        SELECT
            SUM(CASE WHEN dedup_method = 'content_hash' THEN 1 ELSE 0 END) AS content_hash_count,
            SUM(CASE WHEN dedup_method = 'text_hash' THEN 1 ELSE 0 END) AS text_hash_count,
            COUNT(*) AS total_count,
            MAX(created_at) AS last_dedup_at
        FROM attachment_dedup_map
    """)
    dedup_row = cursor.fetchone()
    if dedup_row:
        content_dedups = int(dedup_row[0] or 0)
        text_dedups = int(dedup_row[1] or 0)
        total_dedups = int(dedup_row[2] or 0)
        last_dedup_at = dedup_row[3]
    else:
        content_dedups = text_dedups = total_dedups = 0
        last_dedup_at = None

    # Estimated savings (rough — phase 124 calibration at ~$0.03/Haiku call,
    # ~10s avg for text extraction). Numbers shift over time; treat as a
    # rough lower bound on what dedup is saving.
    AVG_EXTRACTION_SEC = 10.0
    AVG_AI_COST_USD = 0.03
    extractions_avoided = total_dedups
    ai_calls_avoided = total_dedups
    seconds_saved = extractions_avoided * AVG_EXTRACTION_SEC
    dollars_saved = ai_calls_avoided * AVG_AI_COST_USD

    click.echo()
    click.echo(f"  Deduplication (Phase 124)")
    click.echo(f"    total deduped guids   {total_dedups:>8,}")
    click.echo(f"    Layer 3 (content)     {content_dedups:>8,}")
    click.echo(f"    Layer 4 (text)        {text_dedups:>8,}")
    if last_dedup_at:
        click.echo(f"    most recent dedup     {last_dedup_at}")
    else:
        click.echo(f"    most recent dedup     (none yet)")
    click.echo(f"    extractions avoided   {extractions_avoided:>8,}  (~{seconds_saved/60:.1f} min)")
    click.echo(f"    AI calls avoided      {ai_calls_avoided:>8,}  (~${dollars_saved:.2f} @ Haiku)")

    click.echo()
    click.echo("=" * 55)

    cursor.close()
    conn.close()


@click.command("extract-identifiers")
@click.option("--notice-id", type=str, default=None,
              help="Process a single opportunity by notice ID")
@click.option("--batch-size", type=int, default=500, show_default=True,
              help="Number of documents to process per batch")
@click.option("--force", is_flag=True, default=False,
              help="Re-extract even if already processed")
def extract_identifiers(notice_id, batch_size, force):
    """Extract federal identifiers (PIIDs, UEIs, CAGE codes, FAR clauses) from attachment text.

    Scans extracted document text for federal contract identifiers and
    stores them in document_identifier_ref for cross-referencing.

    Examples:
        python main.py extract identifiers
        python main.py extract identifiers --notice-id abc123 --force
        python main.py extract identifiers --batch-size 1000
    """
    logger = setup_logging()

    from etl.attachment_identifier_extractor import AttachmentIdentifierExtractor

    extractor = AttachmentIdentifierExtractor()
    logger.info(
        "Starting identifier extraction (batch_size=%d, force=%s)",
        batch_size, force,
    )
    click.echo(f"Extracting identifiers from attachments (batch_size={batch_size})...")

    stats = extractor.extract_identifiers(
        notice_id=notice_id,
        batch_size=batch_size,
        force=force,
    )

    click.echo(
        f"Done. Processed {stats['documents_processed']} documents, "
        f"found {stats['identifiers_found']} identifiers, "
        f"inserted {stats['identifiers_inserted']} unique refs"
    )


@click.command("cross-ref-identifiers")
@click.option("--notice-id", type=str, default=None,
              help="Only cross-reference identifiers for this opportunity")
@click.option("--batch-size", type=int, default=5000, show_default=True,
              help="Maximum identifiers to check per run")
def cross_ref_identifiers(notice_id, batch_size):
    """Cross-reference extracted identifiers against known DB records.

    Matches PIIDs against fpds_contract, UEIs against entity, CAGE codes
    against entity, etc. Populates matched_table/matched_column/matched_id
    on document_identifier_ref rows.

    Examples:
        python main.py extract cross-ref-identifiers
        python main.py extract cross-ref-identifiers --notice-id abc123
    """
    logger = setup_logging()

    from etl.attachment_identifier_extractor import AttachmentIdentifierExtractor

    extractor = AttachmentIdentifierExtractor()
    logger.info("Starting identifier cross-reference (batch_size=%d)", batch_size)
    click.echo(f"Cross-referencing identifiers (batch_size={batch_size})...")

    stats = extractor.cross_reference(
        notice_id=notice_id,
        batch_size=batch_size,
    )

    click.echo(
        f"Done. Checked {stats['identifiers_checked']} identifiers, "
        f"found {stats['matches_found']} matches"
    )


@click.command("identifiers")
@click.option("--type", "identifier_type", type=str, default=None,
              help="Filter by identifier type (PIID, UEI, CAGE, FAR_CLAUSE, etc.)")
@click.option("--value", "identifier_value", type=str, default=None,
              help="Filter by identifier value (exact or prefix match)")
@click.option("--limit", type=int, default=50, show_default=True,
              help="Maximum results to return")
def search_identifiers(identifier_type, identifier_value, limit):
    """Search for opportunities referencing a specific federal identifier.

    Find which opportunities/documents mention a given PIID, UEI, CAGE
    code, or other federal identifier.

    Examples:
        python main.py search identifiers --type PIID --value 70LGLY21CGLB00003
        python main.py search identifiers --type UEI --value ABCD1234EFG5
        python main.py search identifiers --type FAR_CLAUSE --value 52.219-9
    """
    setup_logging()

    from etl.attachment_identifier_extractor import AttachmentIdentifierExtractor

    extractor = AttachmentIdentifierExtractor()
    results = extractor.search_identifier(
        identifier_type=identifier_type,
        identifier_value=identifier_value,
        limit=limit,
    )

    if not results:
        click.echo("No matching identifiers found.")
        return

    click.echo(f"Found {len(results)} identifier references:\n")
    for row in results:
        matched = ""
        if row.get("matched_table"):
            matched = f" -> {row['matched_table']}.{row['matched_column']}={row['matched_id']}"
        click.echo(
            f"  [{row['identifier_type']}] {row['identifier_value']} "
            f"({row['confidence']}) in {row.get('filename', '?')}"
            f" | notice={row.get('notice_id', '?')}"
            f"{matched}"
        )
        if row.get("opportunity_title"):
            click.echo(f"    Title: {row['opportunity_title'][:100]}")


@click.command("migrate-dedup")
@click.option("--dry-run", is_flag=True, default=False,
              help="Show what would happen without modifying data")
def migrate_dedup(dry_run):
    """Run the attachment deduplication migration (Phase 110ZZZ).

    Migrates from the single-table opportunity_attachment model to a
    normalized 6-table model: sam_attachment, attachment_document,
    opportunity_attachment (map), document_intel_summary,
    document_intel_evidence, and opportunity_attachment_summary.

    Use --dry-run to preview the migration without making changes.

    Examples:
        python main.py maintain migrate-dedup --dry-run
        python main.py maintain migrate-dedup
    """
    logger = setup_logging()

    from etl.attachment_migration import AttachmentDeduplicationMigration

    if dry_run:
        click.echo("DRY RUN — no data will be modified")

    click.echo("Running attachment deduplication migration...")

    migration = AttachmentDeduplicationMigration(dry_run=dry_run)
    stats = migration.run()

    if dry_run:
        report = stats.get("report", [])
        for line in report:
            click.echo(f"  {line}")
        click.echo("DRY RUN complete. No changes were made.")
    else:
        click.echo("Migration complete. Table row counts:")
        for table, count in stats.items():
            if isinstance(count, int):
                click.echo(f"  {table}: {count:,}")


@click.command("backfill-attachment-dedup")
@click.option("--dry-run", is_flag=True, default=False,
              help="Show what would be remapped/deleted without modifying data")
@click.option("--limit", type=int, default=None,
              help="Process at most N groups, then stop. Use to test on a small batch first (e.g. --limit 1).")
@click.option("--attachment-dir", type=str, default=None,
              help="Override the base attachment directory (default: ATTACHMENT_DIR env var)")
def backfill_attachment_dedup(dry_run, limit, attachment_dir):
    """Backfill: clean up existing attachment hash duplicate groups (Phase 124, Task 10).

    Resolves the ~622 content-hash and ~625 text-hash duplicate groups that
    pre-date Phase 124's upstream layers. Processes one group at a time, each
    in its own transaction. Resumable — re-running skips groups already
    recorded in attachment_dedup_map.

    For each duplicate group, the row with the most complete intel
    (highest summary+evidence counts, has AI, has keyword) is chosen as
    canonical. Non-canonicals are remapped in opportunity_attachment, their
    intel rows are deleted, the non-canonical attachment_document row is
    deleted, the physical file is deleted, and sam_attachment.file_path is
    nulled. The sam_attachment row itself is preserved as Layer 1's
    'I've seen this URL' record.

    After running this for real, re-run:
        python main.py backfill opportunity-intel
    to refresh per-opportunity rollups.

    Examples:
        python main.py maintain backfill-attachment-dedup --dry-run
        python main.py maintain backfill-attachment-dedup
    """
    logger = setup_logging()

    from etl.attachment_dedup_backfill import AttachmentDedupBackfill

    if dry_run:
        click.echo("DRY RUN — no DB writes, no files will be deleted")

    click.echo("Scanning attachment_document/sam_attachment for duplicate hash groups...")

    backfill = AttachmentDedupBackfill(attachment_dir=attachment_dir)
    stats = backfill.run(dry_run=dry_run, limit=limit)

    verb = "Would remap" if dry_run else "Remapped"
    verb_del = "Would delete" if dry_run else "Deleted"
    size_mb = stats["bytes_freed"] / (1024 * 1024)

    click.echo("")
    click.echo("=" * 60)
    click.echo("  Attachment Dedup Backfill " + ("Preview" if dry_run else "Results"))
    click.echo("=" * 60)
    click.echo(f"  Groups processed             {stats['groups_processed']:>8,}")
    click.echo(f"    content_hash groups        {stats['by_method']['content_hash']['groups']:>8,}")
    click.echo(f"    text_hash groups           {stats['by_method']['text_hash']['groups']:>8,}")
    click.echo(f"  Groups skipped (empty)       {stats['groups_skipped_empty']:>8,}")
    click.echo(f"  Rows skipped (already done)  {stats['rows_skipped_resumed']:>8,}")
    click.echo("")
    click.echo(f"  {verb} opportunity_attachment {stats['rows_remapped']:>8,}")
    click.echo(f"  {verb_del} attachment_document    {stats['rows_deleted']:>8,}")
    click.echo(f"  {verb_del} document_intel_summary {stats['summary_rows_deleted']:>8,}")
    click.echo(f"  {verb_del} document_intel_evid.   {stats['evidence_rows_deleted']:>8,}")
    click.echo(f"  {verb_del} files                  {stats['files_deleted']:>8,}")
    click.echo(f"    bytes freed                {size_mb:>7.1f} MB")
    click.echo(f"  Files already missing        {stats['files_already_missing']:>8,}")
    click.echo("=" * 60)

    if dry_run:
        click.echo("DRY RUN complete. No changes were made.")
    elif stats["rows_remapped"] or stats["rows_deleted"]:
        click.echo("")
        click.echo("NEXT STEP: re-run rollups to reflect the deduped state:")
        click.echo("  python main.py backfill opportunity-intel")


@click.command("migrate-files")
@click.option("--dry-run", is_flag=True, default=False,
              help="Show what would happen without moving files")
def migrate_files(dry_run):
    """Migrate attachment files to GUID-based directory layout.

    Moves files from {ATTACHMENT_DIR}/{notice_id}/{filename} to
    {ATTACHMENT_DIR}/{resource_guid}/{filename}. Safe to re-run;
    already-moved files are skipped.

    Run this after migrate-dedup completes successfully.

    Examples:
        python main.py maintain migrate-files --dry-run
        python main.py maintain migrate-files
    """
    logger = setup_logging()

    from etl.attachment_migration import AttachmentDeduplicationMigration

    if dry_run:
        click.echo("DRY RUN — no files will be moved")

    click.echo("Migrating attachment files to GUID-based layout...")

    migration = AttachmentDeduplicationMigration(dry_run=dry_run)
    stats = migration._step8_migrate_files()

    verb = "Would move" if dry_run else "Moved"
    click.echo(
        f"Done. {verb} {stats['moved']} files, "
        f"skipped {stats['skipped_already_moved']} already moved, "
        f"{stats['skipped_missing']} missing from disk, "
        f"{stats['failed']} failed"
    )


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
