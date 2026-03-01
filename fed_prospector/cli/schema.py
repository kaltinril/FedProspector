"""Schema drift checking CLI command.

Commands: check-schema
"""

import sys

import click

from config.logging_config import setup_logging


@click.command("check-schema")
@click.option("--fix", is_flag=True, default=False,
              help="Generate ALTER TABLE statements to fix drift (printed to stdout)")
@click.option("--verbose", is_flag=True, default=False,
              help="Show all tables/columns checked, not just mismatches")
@click.option("--table", "table_name", default=None,
              help="Check only a specific table")
def check_schema(fix, verbose, table_name):
    """Compare live database schema against DDL source files.

    Detects missing tables, missing columns, type mismatches,
    missing indexes, missing foreign keys, and missing views.

    Examples:
        python main.py check-schema
        python main.py check-schema --verbose
        python main.py check-schema --table fpds_contract
        python main.py check-schema --fix
    """
    logger = setup_logging()

    from etl.schema_checker import run_schema_check

    try:
        expected_tables, expected_views, live_tables, live_views, drifts = \
            run_schema_check(table_filter=table_name)
    except Exception as e:
        click.echo(f"ERROR: {e}")
        sys.exit(1)

    # Build summary
    table_count = len(expected_tables)
    view_count = len(expected_views)

    click.echo("")
    click.echo("Schema Drift Report")
    click.echo("===================")

    if table_name:
        click.echo(f"Checking table '{table_name}' against DDL files...")
    else:
        click.echo(f"Checking {table_count} tables + {view_count} views against DDL files...")

    click.echo("")

    # Group drifts by table
    drifts_by_table: dict[str, list] = {}
    for d in drifts:
        drifts_by_table.setdefault(d.table, []).append(d)

    ok_count = 0
    drift_count = 0
    missing_count = 0

    # Report on each expected table
    tables_to_report = [table_name.lower()] if table_name else sorted(expected_tables.keys())

    for tname in tables_to_report:
        if tname in drifts_by_table:
            # Check if it's a missing table
            categories = {d.category for d in drifts_by_table[tname]}
            if "missing_table" in categories:
                missing_count += 1
                click.echo(f"MISSING: {tname}")
                for d in drifts_by_table[tname]:
                    click.echo(f"  - {d.detail}")
            elif "not_in_ddl" in categories:
                for d in drifts_by_table[tname]:
                    click.echo(f"ERROR: {d.detail}")
            else:
                drift_count += 1
                click.echo(f"DRIFT: {tname}")
                for d in drifts_by_table[tname]:
                    click.echo(f"  - {d.detail}")
        else:
            ok_count += 1
            if verbose and tname in expected_tables:
                tdef = expected_tables[tname]
                col_count = len(tdef.columns)
                idx_count = len(tdef.indexes)
                click.echo(f"OK: {tname} ({col_count} columns, {idx_count} indexes)")

    # Report extra tables (in DB but not in DDL)
    if not table_name:
        extra_tables = [d for d in drifts if d.category == "extra_table"]
        if extra_tables:
            click.echo("")
            click.echo("Tables in DB but not in DDL:")
            for d in extra_tables:
                click.echo(f"  - {d.table}")

        # Views
        missing_views = [d for d in drifts if d.category == "missing_view"]
        extra_views = [d for d in drifts if d.category == "extra_view"]

        if missing_views or extra_views:
            click.echo("")
        for d in missing_views:
            click.echo(f"MISSING VIEW: {d.table}")
        for d in extra_views:
            click.echo(f"Extra view in DB: {d.table}")

    # Summary line
    click.echo("")
    click.echo(f"Summary: {ok_count} OK, {drift_count} DRIFT, {missing_count} MISSING")

    # Fix mode: output ALTER statements
    fix_items = [d for d in drifts if d.fix_sql]
    if fix and fix_items:
        click.echo("")
        click.echo("-- Fix SQL (review before executing):")
        click.echo("-- " + "=" * 55)
        for d in fix_items:
            click.echo(d.fix_sql)

    if drifts:
        sys.exit(1)
