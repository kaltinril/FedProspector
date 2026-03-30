"""CLI commands for backfilling opportunity columns from extracted intel.

Per-field, frequency-weighted intel backfill.  Each opportunity column is
resolved independently using the best available evidence rather than picking
a single winner row.  Also includes POC backfill from raw staging JSON.
"""

import json
import re

import click
from collections import defaultdict

from config.logging_config import setup_logging


# ---------------------------------------------------------------------------
# Filename-based weights for incumbent keyword fallback (mirrors extractor)
# ---------------------------------------------------------------------------
_FILENAME_WEIGHTS = [
    (re.compile(r"(?:SOW|PWS|statement.of.work)", re.IGNORECASE), 3),
    (re.compile(r"(?:J&A|J\s*&\s*A|justification)", re.IGNORECASE), 2),
    (re.compile(r"(?:RFP|solicitation)", re.IGNORECASE), 2),
    (re.compile(r"(?:Q&A|Q\s*&\s*A|question)", re.IGNORECASE), 1),
]


def _filename_weight(filename):
    """Return document-type weight for a filename (default 1)."""
    if filename:
        for pattern, w in _FILENAME_WEIGHTS:
            if pattern.search(filename):
                return w
    return 1


# ---------------------------------------------------------------------------
# Field mapping: intel field -> (opportunity column, max length or None)
# ---------------------------------------------------------------------------
KEYWORD_PREFERRED_FIELDS = {
    "clearance_required": ("security_clearance_required", 1),
    "vehicle_type": ("contract_vehicle_type", 50),
    "pricing_structure": ("pricing_structure", 50),
    "place_of_performance": ("place_of_performance_detail", 200),
}

AI_PREFERRED_FIELDS = {
    "incumbent_name": ("incumbent_name", 200),
}

# All fields combined for iteration
ALL_FIELDS = {**KEYWORD_PREFERRED_FIELDS, **AI_PREFERRED_FIELDS}

# Keyword/heuristic extraction methods
KEYWORD_METHODS = ("keyword", "heuristic")
AI_METHODS = ("ai_haiku", "ai_sonnet")
AI_RANK = {"ai_haiku": 1, "ai_sonnet": 2}

# Threshold: keyword needs more than this many corroborations to override AI
KEYWORD_OVERRIDE_THRESHOLD = 3


def _resolve_keyword_preferred(intel_rows, field_doc_counts, total_doc_counts,
                               notice_id, field_name):
    """Resolve a keyword-preferred field.

    Returns (value, reason_str) or (None, None).

    Strategy:
      1. Gather keyword/heuristic values with document counts (distinct attachments).
      2. Gather AI values (prefer sonnet > haiku).
      3. Conflict resolution:
         - Both agree -> use that value
         - Keyword N > 3 docs, AI disagrees -> use keyword
         - Keyword N <= 3 docs, AI disagrees -> use AI
         - Only one source -> use it
    """
    # -- Keyword frequency: count distinct documents per value --
    kw_values = {}  # value -> doc_count
    for row in intel_rows:
        if row["extraction_method"] in KEYWORD_METHODS:
            val = row.get(field_name)
            if val and val not in kw_values:
                doc_count = field_doc_counts.get((notice_id, field_name, val), 1)
                kw_values[val] = doc_count

    total_docs = total_doc_counts.get((notice_id, field_name), 0)

    # Best keyword value (most documents)
    kw_best = None
    kw_count = 0
    if kw_values:
        kw_best = max(kw_values, key=kw_values.get)
        kw_count = kw_values[kw_best]

    # -- AI value: prefer sonnet > haiku, latest intel_id as tiebreaker --
    ai_best = None
    ai_method = None
    ai_rank = -1
    ai_best_id = -1
    for row in intel_rows:
        if row["extraction_method"] in AI_METHODS:
            val = row.get(field_name)
            if val:
                r = AI_RANK.get(row["extraction_method"], 0)
                if r > ai_rank or (r == ai_rank and row["intel_id"] > ai_best_id):
                    ai_best = val
                    ai_method = row["extraction_method"]
                    ai_rank = r
                    ai_best_id = row["intel_id"]

    # -- Conflict resolution --
    if kw_best and ai_best:
        if kw_best == ai_best:
            return kw_best, f"keyword+AI agree, {kw_count}/{total_docs} docs"
        elif kw_count > KEYWORD_OVERRIDE_THRESHOLD:
            return kw_best, f"keyword, {kw_count}/{total_docs} docs (overrides AI)"
        else:
            return ai_best, f"AI {ai_method} (keyword has only {kw_count} docs)"
    elif kw_best:
        return kw_best, f"keyword, {kw_count}/{total_docs} docs"
    elif ai_best:
        return ai_best, f"AI {ai_method}"

    return None, None


def _resolve_ai_preferred(intel_rows, field_doc_counts, total_doc_counts,
                          field_name, cursor=None, notice_id=None):
    """Resolve an AI-preferred field (incumbent_name).

    Returns (value, reason_str) or (None, None).

    Strategy:
      1. Prefer AI rows: sonnet > haiku, latest intel_id as tiebreaker.
      2. Fallback to keyword frequency counting with filename-based weighting
         and case-insensitive dedup (requires cursor + notice_id).
    """
    # -- AI value --
    ai_best = None
    ai_method = None
    ai_rank = -1
    ai_best_id = -1
    for row in intel_rows:
        if row["extraction_method"] in AI_METHODS:
            val = row.get(field_name)
            if val:
                r = AI_RANK.get(row["extraction_method"], 0)
                if r > ai_rank or (r == ai_rank and row["intel_id"] > ai_best_id):
                    ai_best = val
                    ai_method = row["extraction_method"]
                    ai_rank = r
                    ai_best_id = row["intel_id"]

    if ai_best:
        return ai_best, f"AI {ai_method}"

    # -- Keyword fallback with filename weighting + case-insensitive dedup --
    if cursor and notice_id and field_name == "incumbent_name":
        cursor.execute("""
            SELECT dis.incumbent_name, sa.filename
            FROM opportunity_attachment oa
            JOIN attachment_document ad ON oa.attachment_id = ad.attachment_id
            JOIN document_intel_summary dis ON ad.document_id = dis.document_id
            LEFT JOIN sam_attachment sa ON oa.attachment_id = sa.attachment_id
            WHERE oa.notice_id = %s
              AND dis.incumbent_name IS NOT NULL
              AND dis.extraction_method IN ('keyword', 'heuristic')
        """, [notice_id])
        kw_rows = cursor.fetchall()

        if kw_rows:
            # Case-insensitive grouping, keep original casing from first seen
            names = {}  # lower_name -> {original, count, weighted_score}
            for r in kw_rows:
                name = r["incumbent_name"]
                key = name.strip().lower()
                weight = _filename_weight(r.get("filename"))
                if key not in names:
                    names[key] = {"original": name, "count": 0,
                                  "weighted_score": 0}
                names[key]["count"] += 1
                names[key]["weighted_score"] += weight

            best = max(names.values(),
                       key=lambda v: (v["weighted_score"], v["count"]))
            total = sum(v["count"] for v in names.values())
            return (best["original"],
                    f"keyword fallback, score {best['weighted_score']}"
                    f" ({best['count']}/{total} docs)")

    # -- Generic keyword fallback (non-incumbent fields, or no cursor) --
    kw_values = {}  # value -> doc_count
    for row in intel_rows:
        if row["extraction_method"] in KEYWORD_METHODS:
            val = row.get(field_name)
            if val and val not in kw_values:
                doc_count = field_doc_counts.get((notice_id, field_name, val), 1) if notice_id else 1
                kw_values[val] = doc_count

    if kw_values:
        total_docs = total_doc_counts.get((notice_id, field_name), 0) if notice_id else sum(kw_values.values())
        kw_best = max(kw_values, key=kw_values.get)
        kw_count = kw_values[kw_best]
        return kw_best, f"keyword fallback, {kw_count}/{total_docs} docs"

    return None, None


def _resolve_uei(cursor, incumbent_name):
    """Resolve incumbent UEI from entity table.

    Returns (uei, reason_str) or (None, None).
    Only returns a UEI when exactly one entity matches.
    """
    if not incumbent_name:
        return None, None

    escaped = incumbent_name.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    cursor.execute(
        "SELECT uei_sam, legal_business_name FROM entity "
        "WHERE legal_business_name LIKE %s LIMIT 2",
        [f"%{escaped}%"],
    )
    matches = cursor.fetchall()
    if len(matches) == 1:
        return matches[0]["uei_sam"], f"entity match: {matches[0]['legal_business_name']}"
    return None, None


# Map document_intel_evidence.field_name → intel column name used by backfill
_SOURCE_FIELD_MAP = {
    "clearance_level": "clearance_required",
    # Others match: vehicle_type, pricing_structure, place_of_performance, incumbent_name
}


def _load_source_counts(cursor, notice_ids):
    """Load document counts per (notice_id, field_name, value) for keyword sources.

    Counts distinct attachments (documents) rather than individual pattern match
    rows.  A single document with 110 mentions of "BPA" counts as 1 doc.

    Returns:
        field_doc_counts: dict of (notice_id, field_name, value) -> distinct_doc_count
        total_doc_counts: dict of (notice_id, field_name) -> total_distinct_docs_with_any_value
    """
    if not notice_ids:
        return {}, {}

    placeholders = ", ".join(["%s"] * len(notice_ids))
    params = list(notice_ids)

    # Per-value document counts
    # Join: evidence -> document_intel_summary -> attachment_document -> opportunity_attachment
    cursor.execute(f"""
        SELECT oa.notice_id, die.field_name,
               CASE die.field_name
                   WHEN 'clearance_level' THEN dis.clearance_required
                   WHEN 'vehicle_type' THEN dis.vehicle_type
                   WHEN 'pricing_structure' THEN dis.pricing_structure
                   WHEN 'place_of_performance' THEN dis.place_of_performance
                   WHEN 'incumbent_name' THEN dis.incumbent_name
               END AS field_value,
               COUNT(DISTINCT die.document_id) AS doc_count
        FROM document_intel_evidence die
        JOIN document_intel_summary dis ON die.intel_id = dis.intel_id
        JOIN attachment_document ad ON dis.document_id = ad.document_id
        JOIN opportunity_attachment oa ON ad.attachment_id = oa.attachment_id
        WHERE oa.notice_id IN ({placeholders})
          AND die.extraction_method IN ('keyword', 'heuristic')
        GROUP BY oa.notice_id, die.field_name, field_value
    """, params)

    field_doc_counts = {}
    for row in cursor.fetchall():
        if row["field_value"] is not None:
            field_name = _SOURCE_FIELD_MAP.get(row["field_name"], row["field_name"])
            field_doc_counts[(row["notice_id"], field_name, row["field_value"])] = row["doc_count"]

    # Total distinct docs per (notice_id, field_name)
    cursor.execute(f"""
        SELECT oa.notice_id, die.field_name,
               COUNT(DISTINCT die.document_id) AS total_docs
        FROM document_intel_evidence die
        JOIN document_intel_summary dis ON die.intel_id = dis.intel_id
        JOIN attachment_document ad ON dis.document_id = ad.document_id
        JOIN opportunity_attachment oa ON ad.attachment_id = oa.attachment_id
        WHERE oa.notice_id IN ({placeholders})
          AND die.extraction_method IN ('keyword', 'heuristic')
        GROUP BY oa.notice_id, die.field_name
    """, params)

    total_doc_counts = {}
    for row in cursor.fetchall():
        field_name = _SOURCE_FIELD_MAP.get(row["field_name"], row["field_name"])
        total_doc_counts[(row["notice_id"], field_name)] = row["total_docs"]

    return field_doc_counts, total_doc_counts


def _load_intel_rows(cursor, notice_ids):
    """Load intel rows for a batch of notice_ids.

    Loads keyword/heuristic rows from opportunity_attachment_summary AND
    AI rows (ai_haiku, ai_sonnet) from document_intel_summary so that
    _resolve_keyword_preferred and _resolve_ai_preferred can see both sources.

    Returns dict of notice_id -> list of intel rows.
    """
    if not notice_ids:
        return {}

    placeholders = ", ".join(["%s"] * len(notice_ids))

    # 1. Keyword/heuristic rows from opportunity_attachment_summary
    cursor.execute(f"""
        SELECT summary_id AS intel_id, notice_id, extraction_method,
               clearance_required,
               vehicle_type, incumbent_name,
               pricing_structure, place_of_performance
        FROM opportunity_attachment_summary
        WHERE notice_id IN ({placeholders})
        ORDER BY notice_id, summary_id
    """, list(notice_ids))

    grouped = defaultdict(list)
    for row in cursor.fetchall():
        grouped[row["notice_id"]].append(row)

    # 2. AI rows from document_intel_summary (ai_haiku, ai_sonnet)
    #    Join through attachment_document -> opportunity_attachment to get notice_id.
    #    For each notice, pick the best AI row per extraction_method
    #    (highest confidence, prefer sonnet over haiku).
    cursor.execute(f"""
        SELECT dis.intel_id, oa.notice_id, dis.extraction_method,
               dis.clearance_required,
               dis.vehicle_type, dis.incumbent_name,
               dis.pricing_structure, dis.place_of_performance
        FROM document_intel_summary dis
        JOIN attachment_document ad ON ad.document_id = dis.document_id
        JOIN opportunity_attachment oa ON oa.attachment_id = ad.attachment_id
        WHERE oa.notice_id IN ({placeholders})
          AND dis.extraction_method IN ('ai_haiku', 'ai_sonnet')
        ORDER BY oa.notice_id,
                 FIELD(dis.extraction_method, 'ai_haiku', 'ai_sonnet'),
                 FIELD(dis.overall_confidence, 'low', 'medium', 'high') DESC,
                 dis.intel_id DESC
    """, list(notice_ids))

    # Keep only the best AI row per (notice_id, extraction_method)
    seen_ai = set()
    for row in cursor.fetchall():
        key = (row["notice_id"], row["extraction_method"])
        if key not in seen_ai:
            seen_ai.add(key)
            grouped[row["notice_id"]].append(row)

    return grouped


@click.command("opportunity-intel")
@click.option("--notice-id", type=str, default=None,
              help="Backfill a single opportunity by notice ID")
@click.option("--dry-run", is_flag=True, default=False,
              help="Show per-field decisions without updating")
@click.option("--verbose", is_flag=True, default=False,
              help="Show detailed reasoning for each field choice")
def backfill_opportunity_intel(notice_id, dry_run, verbose):
    """Backfill opportunity columns from attachment intelligence.

    Each field is resolved independently using the best available evidence:
    keyword frequency counts, AI extraction, or a combination of both.

    Keyword-preferred fields (clearance, vehicle, pricing, place of performance)
    use frequency-weighted keyword evidence, falling back to AI.

    AI-preferred fields (incumbent_name) prefer AI extraction, falling back
    to keyword frequency.

    After resolving incumbent_name, UEI resolution looks up the entity table
    for an exact-one match.

    Examples:
        python main.py backfill opportunity-intel
        python main.py backfill opportunity-intel --notice-id abc123
        python main.py backfill opportunity-intel --dry-run --verbose
    """
    logger = setup_logging()

    from db.connection import get_connection

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Get all notice_ids that have intel rows (keyword OR AI)
        if notice_id:
            cursor.execute(
                "SELECT DISTINCT notice_id FROM opportunity_attachment_summary "
                "WHERE notice_id = %s "
                "UNION "
                "SELECT DISTINCT oa.notice_id "
                "FROM document_intel_summary dis "
                "JOIN attachment_document ad ON ad.document_id = dis.document_id "
                "JOIN opportunity_attachment oa ON oa.attachment_id = ad.attachment_id "
                "WHERE oa.notice_id = %s "
                "  AND dis.extraction_method IN ('ai_haiku', 'ai_sonnet')",
                [notice_id, notice_id]
            )
        else:
            cursor.execute(
                "SELECT DISTINCT notice_id FROM opportunity_attachment_summary "
                "UNION "
                "SELECT DISTINCT oa.notice_id "
                "FROM document_intel_summary dis "
                "JOIN attachment_document ad ON ad.document_id = dis.document_id "
                "JOIN opportunity_attachment oa ON oa.attachment_id = ad.attachment_id "
                "WHERE dis.extraction_method IN ('ai_haiku', 'ai_sonnet')"
            )
        all_notice_ids = [r["notice_id"] for r in cursor.fetchall()]

        if not all_notice_ids:
            click.echo("No intel rows found to backfill.")
            return

        total_notices = len(all_notice_ids)
        click.echo(f"Processing {total_notices} opportunities with intel data...")

        # Process in batches for efficiency
        BATCH_SIZE = 500
        total_updated = 0
        total_skipped = 0
        total_fields = 0
        stats = {"keyword": 0, "ai": 0, "fallback": 0, "uei": 0}

        for batch_start in range(0, len(all_notice_ids), BATCH_SIZE):
            batch_ids = all_notice_ids[batch_start:batch_start + BATCH_SIZE]
            batch_num = batch_start // BATCH_SIZE + 1
            total_batches = (total_notices + BATCH_SIZE - 1) // BATCH_SIZE
            click.echo(
                f"  Batch {batch_num}/{total_batches} "
                f"({batch_start + 1}-{min(batch_start + BATCH_SIZE, total_notices)}"
                f"/{total_notices})...",
                nl=False,
            )

            # Load intel rows and source counts for this batch
            intel_by_notice = _load_intel_rows(cursor, batch_ids)
            field_doc_counts, total_doc_counts = _load_source_counts(cursor, batch_ids)

            for nid in batch_ids:
                rows = intel_by_notice.get(nid, [])
                if not rows:
                    total_skipped += 1
                    continue

                updates = []
                update_params = []
                field_decisions = []

                # Resolve keyword-preferred fields
                for intel_field, (opp_col, max_len) in KEYWORD_PREFERRED_FIELDS.items():
                    value, reason = _resolve_keyword_preferred(
                        rows, field_doc_counts, total_doc_counts,
                        nid, intel_field
                    )
                    if value:
                        if max_len:
                            value = value[:max_len]
                        updates.append(f"{opp_col} = %s")
                        update_params.append(value)
                        total_fields += 1
                        field_decisions.append((opp_col, value, reason))

                        # Categorize for stats
                        if "keyword+AI agree" in reason:
                            stats["keyword"] += 1
                        elif "keyword" in reason and "AI" not in reason:
                            stats["keyword"] += 1
                        elif "AI" in reason and "keyword" not in reason:
                            stats["ai"] += 1
                        elif "overrides" in reason:
                            stats["keyword"] += 1
                        else:
                            stats["fallback"] += 1

                # Resolve AI-preferred fields
                for intel_field, (opp_col, max_len) in AI_PREFERRED_FIELDS.items():
                    value, reason = _resolve_ai_preferred(
                        rows, field_doc_counts, total_doc_counts,
                        intel_field, cursor=cursor, notice_id=nid,
                    )
                    if value:
                        if max_len:
                            value = value[:max_len]
                        updates.append(f"{opp_col} = %s")
                        update_params.append(value)
                        total_fields += 1
                        field_decisions.append((opp_col, value, reason))

                        if "AI" in reason and "fallback" not in reason:
                            stats["ai"] += 1
                        elif "keyword fallback" in reason:
                            stats["fallback"] += 1
                        else:
                            stats["fallback"] += 1

                    # UEI resolution for incumbent
                    if intel_field == "incumbent_name" and value:
                        uei, uei_reason = _resolve_uei(cursor, value)
                        if uei:
                            updates.append("incumbent_uei = %s")
                            update_params.append(uei)
                            stats["uei"] += 1
                            field_decisions.append(("incumbent_uei", uei, uei_reason))

                if not updates:
                    total_skipped += 1
                    continue

                # Print per-notice detail only in verbose mode
                if verbose:
                    click.echo(f"Notice {nid}:")
                    for col, val, reason in field_decisions:
                        click.echo(f"  {col} = {val} ({reason})")

                if dry_run:
                    total_updated += 1
                    continue

                # Execute UPDATE
                update_params.append(nid)
                cursor.execute(
                    f"UPDATE opportunity SET {', '.join(updates)} WHERE notice_id = %s",
                    update_params,
                )
                if cursor.rowcount > 0:
                    total_updated += 1
                else:
                    total_skipped += 1

            # Commit per batch (not per row)
            if not dry_run:
                conn.commit()

            click.echo(f" {total_updated} updated, {total_fields} fields so far")

        # Summary
        verb = "Would update" if dry_run else "Updated"
        click.echo(
            f"\nDone. {verb} {total_updated} opportunities ({total_fields} fields)."
        )
        click.echo(f"  By keyword frequency: {stats['keyword']} fields")
        click.echo(f"  By AI: {stats['ai']} fields")
        click.echo(f"  By fallback (only source): {stats['fallback']} fields")
        click.echo(f"  Incumbent UEI resolved: {stats['uei']}")

        if total_skipped:
            click.echo(
                f"  Skipped: {total_skipped} "
                f"(no relevant intel or no matching opportunity)"
            )

    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


# ---------------------------------------------------------------------------
# POC backfill from stg_opportunity_raw
# ---------------------------------------------------------------------------

def _parse_pocs_from_raw(raw_json):
    """Extract POC dicts from a raw opportunity JSON object.

    Returns list of dicts with keys: full_name, email, phone, fax, title, officer_type.
    Mirrors the extraction logic in opportunity_loader._normalize_opportunity.
    """
    pocs = []
    for poc in (raw_json.get("pointOfContact") or []):
        if not isinstance(poc, dict):
            continue
        full_name = (poc.get("fullName") or "").strip()
        if not full_name:
            continue
        pocs.append({
            "full_name":    full_name[:500],
            "email":        ((poc.get("email") or "").strip()[:200]) or None,
            "phone":        ((poc.get("phone") or "").strip()[:100]) or None,
            "fax":          ((poc.get("fax") or "").strip()[:100]) or None,
            "title":        ((poc.get("title") or "").strip()[:200]) or None,
            "officer_type": ((poc.get("type") or "").strip()[:50]) or None,
        })
    return pocs


def _upsert_pocs(cursor, notice_id, pocs):
    """Upsert POC records — mirrors opportunity_loader._upsert_pocs."""
    officer_sql = (
        "INSERT INTO contracting_officer "
        "(full_name, email, phone, fax, title, officer_type) "
        "VALUES (%s, %s, %s, %s, %s, %s) "
        "ON DUPLICATE KEY UPDATE "
        "phone = COALESCE(VALUES(phone), phone), "
        "fax = COALESCE(VALUES(fax), fax), "
        "title = COALESCE(VALUES(title), title), "
        "officer_type = COALESCE(VALUES(officer_type), officer_type)"
    )
    poc_link_sql = (
        "INSERT INTO opportunity_poc (notice_id, officer_id, poc_type) "
        "VALUES (%s, %s, %s) "
        "ON DUPLICATE KEY UPDATE poc_type = VALUES(poc_type)"
    )

    for poc in pocs:
        cursor.execute(officer_sql, (
            poc["full_name"], poc["email"], poc["phone"],
            poc["fax"], poc["title"], poc["officer_type"],
        ))
        officer_id = cursor.lastrowid
        if officer_id == 0:
            cursor.execute(
                "SELECT officer_id FROM contracting_officer "
                "WHERE full_name = %s AND email = %s",
                (poc["full_name"], poc["email"]),
            )
            row = cursor.fetchone()
            if row is None:
                continue
            officer_id = row["officer_id"]

        poc_type = (poc["officer_type"] or "PRIMARY").upper()
        cursor.execute(poc_link_sql, (notice_id, officer_id, poc_type))


@click.command("pocs")
@click.option("--notice-id", type=str, default=None,
              help="Backfill POCs for a single opportunity")
@click.option("--dry-run", is_flag=True, default=False,
              help="Show what would be backfilled without writing")
@click.option("--force", is_flag=True, default=False,
              help="Re-extract POCs even for opportunities that already have them")
def backfill_pocs(notice_id, dry_run, force):
    """Backfill Point of Contact data from raw staging JSON.

    Extracts pointOfContact data from stg_opportunity_raw.raw_json and
    populates the contracting_officer and opportunity_poc tables.

    By default, only processes opportunities that have no POC records yet.
    Use --force to re-extract for all opportunities.

    Examples:
        python main.py backfill pocs
        python main.py backfill pocs --notice-id abc123
        python main.py backfill pocs --dry-run
        python main.py backfill pocs --force
    """
    logger = setup_logging()

    from db.connection import get_connection

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Find opportunities to process
        if notice_id:
            if force:
                cursor.execute(
                    "SELECT DISTINCT notice_id FROM stg_opportunity_raw "
                    "WHERE notice_id = %s",
                    [notice_id],
                )
            else:
                cursor.execute(
                    "SELECT DISTINCT s.notice_id FROM stg_opportunity_raw s "
                    "LEFT JOIN opportunity_poc p ON s.notice_id = p.notice_id "
                    "WHERE s.notice_id = %s AND p.poc_id IS NULL",
                    [notice_id],
                )
        else:
            if force:
                cursor.execute(
                    "SELECT DISTINCT notice_id FROM stg_opportunity_raw"
                )
            else:
                cursor.execute(
                    "SELECT DISTINCT s.notice_id FROM stg_opportunity_raw s "
                    "LEFT JOIN opportunity_poc p ON s.notice_id = p.notice_id "
                    "WHERE p.poc_id IS NULL"
                )

        target_ids = [r["notice_id"] for r in cursor.fetchall()]

        if not target_ids:
            click.echo("No opportunities need POC backfill.")
            return

        click.echo(f"Processing {len(target_ids)} opportunities...")

        BATCH_SIZE = 500
        total_processed = 0
        total_pocs = 0
        total_skipped = 0

        for batch_start in range(0, len(target_ids), BATCH_SIZE):
            batch_ids = target_ids[batch_start:batch_start + BATCH_SIZE]
            batch_num = batch_start // BATCH_SIZE + 1
            total_batches = (len(target_ids) + BATCH_SIZE - 1) // BATCH_SIZE

            click.echo(
                f"  Batch {batch_num}/{total_batches}...",
                nl=False,
            )

            # Get the latest raw_json for each notice_id in this batch
            placeholders = ", ".join(["%s"] * len(batch_ids))
            cursor.execute(f"""
                SELECT s1.notice_id, s1.raw_json
                FROM stg_opportunity_raw s1
                INNER JOIN (
                    SELECT notice_id, MAX(id) AS max_id
                    FROM stg_opportunity_raw
                    WHERE notice_id IN ({placeholders})
                    GROUP BY notice_id
                ) s2 ON s1.id = s2.max_id
            """, batch_ids)

            rows = cursor.fetchall()

            for row in rows:
                nid = row["notice_id"]
                raw = row["raw_json"]
                if isinstance(raw, str):
                    raw = json.loads(raw)

                pocs = _parse_pocs_from_raw(raw)
                if not pocs:
                    total_skipped += 1
                    continue

                if dry_run:
                    for poc in pocs:
                        click.echo(
                            f"\n    {nid}: {poc['full_name']} "
                            f"<{poc['email'] or 'no email'}> "
                            f"({poc['officer_type'] or 'PRIMARY'})"
                        )
                    total_processed += 1
                    total_pocs += len(pocs)
                    continue

                _upsert_pocs(cursor, nid, pocs)
                total_processed += 1
                total_pocs += len(pocs)

            if not dry_run:
                conn.commit()

            click.echo(f" {total_processed} opps, {total_pocs} POCs so far")

        verb = "Would process" if dry_run else "Processed"
        click.echo(
            f"\nDone. {verb} {total_processed} opportunities, "
            f"{total_pocs} POC records."
        )
        if total_skipped:
            click.echo(f"  Skipped: {total_skipped} (no POC data in raw JSON)")

    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()
