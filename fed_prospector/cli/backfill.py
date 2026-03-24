"""CLI commands for backfilling opportunity columns from extracted intel (Phase 110C)."""

import click

from config.logging_config import setup_logging


@click.command("opportunity-intel")
@click.option("--notice-id", type=str, default=None,
              help="Backfill a single opportunity by notice ID")
@click.option("--dry-run", is_flag=True, default=False,
              help="Show what would be updated without making changes")
def backfill_opportunity_intel(notice_id, dry_run):
    """Backfill opportunity columns from attachment intelligence.

    Updates security_clearance_required, incumbent_name, and
    contract_vehicle_type on the opportunity table using the best
    available intel from opportunity_attachment_intel.

    This is useful after AI analysis upgrades intel quality, or to
    ensure all opportunities reflect their latest extracted data.

    Examples:
        python main.py backfill opportunity-intel
        python main.py backfill opportunity-intel --notice-id abc123
        python main.py backfill opportunity-intel --dry-run
    """
    logger = setup_logging()

    from db.connection import get_connection

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Build the query to find best intel per notice_id.
        # AI methods override keyword methods; higher confidence wins within same method.
        # Use FIELD() to rank extraction_method: ai_sonnet > ai_haiku > heuristic > keyword
        where = ""
        params = []
        if notice_id:
            where = "WHERE oai.notice_id = %s"
            params = [notice_id]

        # Find best intel per notice_id using ranked extraction methods.
        # Pick one row per notice_id: best method, best confidence, latest intel_id as tiebreaker.
        notice_filter = ""
        if notice_id:
            notice_filter = "WHERE notice_id = %s"

        cursor.execute(f"""
            SELECT notice_id, clearance_required, vehicle_type, incumbent_name
            FROM opportunity_attachment_intel
            WHERE intel_id IN (
                SELECT MAX(intel_id) FROM (
                    SELECT intel_id, notice_id,
                           FIELD(extraction_method, 'keyword','heuristic','ai_dry_run','ai_haiku','ai_sonnet') * 100 +
                           FIELD(overall_confidence, 'low','medium','high') AS rank_score
                    FROM opportunity_attachment_intel
                    {notice_filter}
                ) ranked
                INNER JOIN (
                    SELECT notice_id AS nid,
                           MAX(FIELD(extraction_method, 'keyword','heuristic','ai_dry_run','ai_haiku','ai_sonnet') * 100 +
                               FIELD(overall_confidence, 'low','medium','high')) AS best_rank
                    FROM opportunity_attachment_intel
                    {notice_filter}
                    GROUP BY notice_id
                ) best ON ranked.notice_id = best.nid AND ranked.rank_score = best.best_rank
                GROUP BY ranked.notice_id
            )
        """, params + params)

        intel_rows = cursor.fetchall()

        if not intel_rows:
            click.echo("No intel rows found to backfill.")
            return

        updated = 0
        skipped = 0

        for row in intel_rows:
            updates = []
            update_params = []

            if row["clearance_required"]:
                updates.append("security_clearance_required = %s")
                update_params.append(row["clearance_required"])

            if row["vehicle_type"]:
                updates.append("contract_vehicle_type = LEFT(%s, 50)")
                update_params.append(row["vehicle_type"])

            if row["incumbent_name"]:
                updates.append("incumbent_name = %s")
                update_params.append(row["incumbent_name"])

            if not updates:
                skipped += 1
                continue

            if dry_run:
                click.echo(
                    f"  Would update {row['notice_id']}: "
                    + ", ".join(f"{u.split(' =')[0]}={p}" for u, p in zip(updates, update_params))
                )
                updated += 1
                continue

            update_params.append(row["notice_id"])
            cursor.execute(
                f"UPDATE opportunity SET {', '.join(updates)} WHERE notice_id = %s",
                update_params,
            )
            if cursor.rowcount > 0:
                updated += 1
            else:
                skipped += 1

        if not dry_run:
            conn.commit()

        verb = "Would update" if dry_run else "Updated"
        click.echo(
            f"Done. {verb} {updated} opportunities, skipped {skipped} "
            f"(no relevant intel or no matching opportunity)"
        )

    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()
