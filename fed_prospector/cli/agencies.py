"""Agency code normalization CLI commands.

Commands: normalize-agencies, unresolved-agencies, normalize-fh-orgs
"""

import sys

import click

from config.logging_config import setup_logging


@click.command("normalize-agencies")
@click.option("--refetch-missing", is_flag=True, help="Re-fetch from SAM.gov API for opportunities missing from staging")
@click.option("--dry-run", is_flag=True, help="Preview changes without writing to database")
def normalize_agencies(refetch_missing, dry_run):
    """Backfill agency CGAC codes on opportunity and usaspending_award tables.

    Two-pass approach for opportunities:
      Pass 1: Extract from stored raw JSON in stg_opportunity_raw
      Pass 2: Use agency_resolver for any still-NULL records

    USASpending uses agency_resolver for name-to-code resolution.

    Examples:
        python main.py maintain normalize-agencies
        python main.py maintain normalize-agencies --dry-run
        python main.py maintain normalize-agencies --refetch-missing
    """
    import time

    logger = setup_logging()

    from etl.agency_resolver import AgencyResolver
    from db.connection import get_connection

    t_start = time.time()

    try:
        # -----------------------------------------------------------------
        # Opportunity backfill
        # -----------------------------------------------------------------

        # Pass 1: Extract CGAC from stored raw JSON
        click.echo("Pass 1: Extracting agency codes from stored raw JSON...")
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM opportunity WHERE department_cgac IS NULL
        """)
        null_before = cursor.fetchone()[0]

        if not dry_run:
            cursor.execute("""
                UPDATE opportunity o
                JOIN stg_opportunity_raw s ON o.notice_id = s.notice_id
                SET o.department_cgac = SUBSTRING_INDEX(
                        JSON_UNQUOTE(JSON_EXTRACT(s.raw_json, '$.fullParentPathCode')), '.', 1),
                    o.sub_tier_code = SUBSTRING_INDEX(
                        SUBSTRING_INDEX(JSON_UNQUOTE(JSON_EXTRACT(s.raw_json, '$.fullParentPathCode')), '.', 2), '.', -1)
                WHERE o.department_cgac IS NULL
                  AND JSON_EXTRACT(s.raw_json, '$.fullParentPathCode') IS NOT NULL
            """)
            conn.commit()

        cursor.execute("""
            SELECT COUNT(*) FROM opportunity WHERE department_cgac IS NULL
        """)
        null_after = cursor.fetchone()[0]
        resolved_json = null_before - null_after
        click.echo(f"  Resolved from JSON: {resolved_json:,}")
        click.echo(f"  Still NULL:         {null_after:,}")

        # Pass 2: Resolve remaining via agency name lookup
        if null_after > 0:
            click.echo("\nPass 2: Resolving remaining via agency name lookup...")
            resolver = AgencyResolver()
            cursor.execute("""
                SELECT DISTINCT department_name
                FROM opportunity
                WHERE department_cgac IS NULL AND department_name IS NOT NULL
            """)
            names = [row[0] for row in cursor.fetchall()]
            mapping = resolver.resolve_bulk(names)
            resolved_count = 0
            if not dry_run:
                for name, cgac in mapping.items():
                    if cgac:
                        cursor.execute("""
                            UPDATE opportunity SET department_cgac = %s
                            WHERE department_name = %s AND department_cgac IS NULL
                        """, (cgac, name))
                        resolved_count += cursor.rowcount
                conn.commit()
            else:
                resolved_count = sum(1 for v in mapping.values() if v)
            stats = resolver.get_stats()
            click.echo(f"  Resolved from names: {resolved_count:,}")
            click.echo(f"  Match breakdown: exact={stats['exact']}, variant={stats['variant']}, fuzzy={stats['fuzzy']}, unresolved={stats['unresolved']}")

        # -----------------------------------------------------------------
        # USASpending backfill — resolve distinct names first, then
        # update per-name (hits idx_usa_agency index, avoids full scan)
        # -----------------------------------------------------------------

        click.echo("\nUSASpending: Resolving agency codes...")

        # Build resolver once for both awarding + funding
        resolver = AgencyResolver()

        for cgac_col, name_col, label in [
            ("awarding_agency_cgac", "awarding_agency_name", "Awarding"),
            ("funding_agency_cgac", "funding_agency_name", "Funding"),
        ]:
            cursor.execute(f"""
                SELECT {name_col}, COUNT(*) as cnt
                FROM usaspending_award
                WHERE {cgac_col} IS NULL AND {name_col} IS NOT NULL
                GROUP BY {name_col}
                ORDER BY cnt DESC
            """)
            name_rows = cursor.fetchall()
            total_null = sum(r[1] for r in name_rows)
            click.echo(f"\n  {label} agency NULL: {total_null:,} rows across {len(name_rows)} distinct names")

            if not name_rows:
                continue

            names = [r[0] for r in name_rows]
            mapping = resolver.resolve_bulk(names)
            stats = resolver.get_stats()
            resolved_names = {n: c for n, c in mapping.items() if c}
            click.echo(f"  Resolver: {stats['exact']} exact, {stats['variant']} variant, {stats['fuzzy']} fuzzy, {stats['unresolved']} unresolved")
            click.echo(f"  Updating {len(resolved_names)} resolved names...")

            total_updated = 0
            for i, (name, cgac) in enumerate(resolved_names.items(), 1):
                if not dry_run:
                    cursor.execute(f"""
                        UPDATE usaspending_award SET {cgac_col} = %s
                        WHERE {name_col} = %s AND {cgac_col} IS NULL
                    """, (cgac, name))
                    total_updated += cursor.rowcount
                    conn.commit()
                if i % 10 == 0 or i == len(resolved_names):
                    click.echo(f"    {i}/{len(resolved_names)} names done ({total_updated:,} rows updated)")

            click.echo(f"  {label} total rows updated: {total_updated:,}")

        # -----------------------------------------------------------------
        # Summary
        # -----------------------------------------------------------------

        elapsed = time.time() - t_start
        click.echo(f"\nDone in {elapsed:.1f} seconds.")
        cursor.close()
        conn.close()

    except Exception as e:
        elapsed = time.time() - t_start
        logger.exception("Agency normalization failed")
        click.echo("\nERROR after %.1f seconds: %s" % (elapsed, e))
        sys.exit(1)


@click.command("unresolved-agencies")
@click.option("--limit", default=50, show_default=True, help="Max unresolved names to show per table")
def unresolved_agencies(limit):
    """Report agency names that have no CGAC code.

    Shows unmatched agency names by source table, sorted by row count
    (highest impact first). Helps identify gaps in federal_organization data.

    Examples:
        python main.py report unresolved-agencies
        python main.py report unresolved-agencies --limit 100
    """
    from db.connection import get_connection

    logger = setup_logging()

    try:
        conn = get_connection()
        cursor = conn.cursor()

        tables = [
            ("opportunity", "department_name", "department_cgac"),
            ("usaspending_award", "awarding_agency_name", "awarding_agency_cgac"),
            ("usaspending_award", "funding_agency_name", "funding_agency_cgac"),
        ]

        for table, name_col, cgac_col in tables:
            click.echo(f"\n{'='*60}")
            click.echo(f"  {table}.{name_col} (code: {cgac_col})")
            click.echo(f"{'='*60}")

            cursor.execute(f"""
                SELECT {name_col}, COUNT(*) as cnt
                FROM {table}
                WHERE {cgac_col} IS NULL AND {name_col} IS NOT NULL
                GROUP BY {name_col}
                ORDER BY cnt DESC
                LIMIT %s
            """, (limit,))

            rows = cursor.fetchall()
            if not rows:
                click.echo("  All resolved!")
                continue

            total = sum(r[1] for r in rows)
            click.echo(f"  Total unresolved rows: {total:,}")
            click.echo(f"  Top {len(rows)} unresolved names:")
            click.echo(f"  {'Agency Name':<60} {'Count':>10}")
            click.echo(f"  {'-'*60} {'-'*10}")
            for name, cnt in rows:
                display = (name[:57] + "...") if len(name) > 60 else name
                click.echo(f"  {display:<60} {cnt:>10,}")

        cursor.close()
        conn.close()

    except Exception as e:
        logger.exception("Unresolved agencies report failed")
        click.echo(f"\nERROR: {e}")
        sys.exit(1)


@click.command("normalize-fh-orgs")
@click.option("--table", type=click.Choice(["opportunity", "fpds", "usaspending", "all"]),
              default="all", show_default=True, help="Which table(s) to backfill")
@click.option("--dry-run", is_flag=True, help="Preview changes without writing to database")
def normalize_fh_orgs(table, dry_run):
    """Backfill fh_org_id on opportunity, fpds_contract, and usaspending_award.

    Resolves each record's awarding agency to a federal_organization.fh_org_id
    using code joins (opportunity, FPDS) or name matching + alias table (USASpending).
    Only updates rows where fh_org_id IS NULL, so safe to run repeatedly.

    Examples:
        python main.py maintain normalize-fh-orgs
        python main.py maintain normalize-fh-orgs --table opportunity
        python main.py maintain normalize-fh-orgs --table fpds
        python main.py maintain normalize-fh-orgs --table usaspending
        python main.py maintain normalize-fh-orgs --dry-run
    """
    import time

    logger = setup_logging()

    from db.connection import get_connection

    t_start = time.time()

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # -----------------------------------------------------------------
        # Opportunity backfill
        # -----------------------------------------------------------------
        if table in ("opportunity", "all"):
            click.echo("=== Opportunity fh_org_id backfill ===")

            cursor.execute("SELECT COUNT(*) FROM opportunity WHERE fh_org_id IS NULL")
            null_before = cursor.fetchone()[0]
            click.echo(f"  NULL before: {null_before:,}")

            if not dry_run:
                # Step 1: sub_tier_code -> Sub-Tier org
                cursor.execute("""
                    UPDATE opportunity o
                    JOIN federal_organization fo
                      ON fo.agency_code = o.sub_tier_code AND fo.fh_org_type = 'Sub-Tier'
                    SET o.fh_org_id = fo.fh_org_id
                    WHERE o.fh_org_id IS NULL AND o.sub_tier_code IS NOT NULL
                """)
                step1 = cursor.rowcount
                conn.commit()
                click.echo(f"  Step 1 (sub_tier_code): {step1:,} rows")

                # Step 2: department CGAC fallback
                cursor.execute("""
                    UPDATE opportunity o
                    JOIN federal_organization fo
                      ON fo.cgac = o.department_cgac
                      AND fo.fh_org_type = 'Department/Ind. Agency' AND fo.level = 1
                    SET o.fh_org_id = fo.fh_org_id
                    WHERE o.fh_org_id IS NULL AND o.department_cgac IS NOT NULL
                """)
                step2 = cursor.rowcount
                conn.commit()
                click.echo(f"  Step 2 (dept CGAC):     {step2:,} rows")

            cursor.execute("SELECT COUNT(*) FROM opportunity WHERE fh_org_id IS NULL")
            null_after = cursor.fetchone()[0]
            click.echo(f"  NULL after:  {null_after:,}")

        # -----------------------------------------------------------------
        # FPDS backfill
        # -----------------------------------------------------------------
        if table in ("fpds", "all"):
            click.echo("\n=== FPDS fh_org_id backfill ===")

            cursor.execute("SELECT COUNT(*) FROM fpds_contract WHERE fh_org_id IS NULL")
            null_before = cursor.fetchone()[0]
            click.echo(f"  NULL before: {null_before:,}")

            if not dry_run:
                # Step 1: oldfpds_office_code match
                cursor.execute("""
                    UPDATE fpds_contract fc
                    JOIN (
                        SELECT oldfpds_office_code, MIN(fh_org_id) as fh_org_id
                        FROM federal_organization
                        WHERE oldfpds_office_code IS NOT NULL
                        GROUP BY oldfpds_office_code
                    ) fo ON fo.oldfpds_office_code = fc.contracting_office_id
                    SET fc.fh_org_id = fo.fh_org_id
                    WHERE fc.fh_org_id IS NULL AND fc.contracting_office_id IS NOT NULL
                """)
                step1 = cursor.rowcount
                conn.commit()
                click.echo(f"  Step 1 (office code):   {step1:,} rows")

                # Step 2: department-level fallback via agency_id
                cursor.execute("""
                    UPDATE fpds_contract fc
                    JOIN (
                        SELECT agency_code, MIN(fh_org_id) as fh_org_id
                        FROM federal_organization
                        WHERE fh_org_type = 'Department/Ind. Agency' AND level = 1
                        GROUP BY agency_code
                    ) fo ON fo.agency_code = fc.agency_id
                    SET fc.fh_org_id = fo.fh_org_id
                    WHERE fc.fh_org_id IS NULL AND fc.agency_id IS NOT NULL
                """)
                step2 = cursor.rowcount
                conn.commit()
                click.echo(f"  Step 2 (agency_id):     {step2:,} rows")

            cursor.execute("SELECT COUNT(*) FROM fpds_contract WHERE fh_org_id IS NULL")
            null_after = cursor.fetchone()[0]
            click.echo(f"  NULL after:  {null_after:,}")

        # -----------------------------------------------------------------
        # USASpending backfill
        # -----------------------------------------------------------------
        if table in ("usaspending", "all"):
            click.echo("\n=== USASpending fh_org_id backfill ===")

            if not dry_run:
                # Step 1: Build mapping from distinct names via federal_organization
                click.echo("  Step 1: building name→fh_org_id mapping...")
                cursor.execute("""
                    SELECT DISTINCT ua.awarding_sub_agency_name, ua.awarding_agency_cgac
                    FROM usaspending_award ua
                    WHERE ua.fh_org_id IS NULL
                      AND ua.awarding_sub_agency_name IS NOT NULL
                      AND ua.awarding_agency_cgac IS NOT NULL
                """)
                name_cgac_pairs = cursor.fetchall()

                # Build lookup from federal_organization
                cursor.execute("""
                    SELECT fh_org_id, fh_org_name, cgac
                    FROM federal_organization
                    WHERE fh_org_type = 'Sub-Tier'
                """)
                fo_map = {}
                for fh_org_id, fh_org_name, cgac in cursor.fetchall():
                    key = (fh_org_name.strip().upper() if fh_org_name else "", cgac or "")
                    fo_map[key] = fh_org_id

                # Load alias table
                cursor.execute("SELECT source_name, fh_org_id FROM agency_name_alias")
                alias_map = {row[0]: row[1] for row in cursor.fetchall()}

                # Resolve each name to fh_org_id
                resolved = []
                for sub_name, cgac in name_cgac_pairs:
                    key = (sub_name.strip().upper() if sub_name else "", cgac or "")
                    fh_id = fo_map.get(key)
                    if fh_id is None:
                        fh_id = alias_map.get(sub_name)
                    if fh_id is not None:
                        resolved.append((fh_id, sub_name, cgac))

                click.echo(f"  Resolved {len(resolved)} of {len(name_cgac_pairs)} distinct name+CGAC combos")

                # Create temp index for fast per-name UPDATEs
                click.echo("  Creating temporary index on awarding_sub_agency_name (this takes a few minutes)...")
                t_idx = time.time()
                cursor.execute("""
                    ALTER TABLE usaspending_award
                    ADD INDEX idx_usa_sub_agency_tmp (awarding_sub_agency_name(50))
                """)
                click.echo(f"  Index built in {time.time() - t_idx:.1f}s")

                # Per-name UPDATEs with progress
                click.echo(f"  Step 2: applying {len(resolved)} per-name UPDATEs...")
                step1 = 0
                for i, (fh_id, sub_name, cgac) in enumerate(resolved, 1):
                    cursor.execute(
                        "UPDATE usaspending_award SET fh_org_id = %s "
                        "WHERE awarding_sub_agency_name = %s "
                        "AND awarding_agency_cgac = %s "
                        "AND fh_org_id IS NULL",
                        (fh_id, sub_name, cgac),
                    )
                    rows = cursor.rowcount
                    step1 += rows
                    conn.commit()
                    click.echo(f"    [{i}/{len(resolved)}] {sub_name} ({cgac}): {rows:,} rows")

                click.echo(f"  Total resolved: {step1:,} rows")

                # Drop temp index
                click.echo("  Dropping temporary index...")
                cursor.execute("ALTER TABLE usaspending_award DROP INDEX idx_usa_sub_agency_tmp")
                click.echo("  Done.")

            # Skip COUNT(*) on 28M rows — per-name progress above shows the total

        # -----------------------------------------------------------------
        # Summary
        # -----------------------------------------------------------------
        elapsed = time.time() - t_start
        click.echo(f"\nDone in {elapsed:.1f} seconds.")
        cursor.close()
        conn.close()

    except Exception as e:
        elapsed = time.time() - t_start
        logger.exception("fh_org_id normalization failed")
        click.echo("\nERROR after %.1f seconds: %s" % (elapsed, e))
        sys.exit(1)
