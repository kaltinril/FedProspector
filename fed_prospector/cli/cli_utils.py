"""Shared utilities for CLI commands.

Provides three reusable helpers that eliminate duplication across the 10+
CLI command modules:

  print_table(columns, rows)       -- fixed-width ASCII table output
  echo_load_stats(stats)           -- standard 5-line ETL stats block
  QueryBuilder                     -- accumulates SQL WHERE conditions
"""

import click


def print_table(columns: list[dict], rows: list) -> None:
    """Print a fixed-width ASCII table to stdout.

    columns: list of {"header": str, "width": int}
             e.g. [{"header": "PIID", "width": 17}, {"header": "VENDOR", "width": 30}]
    rows:    list of sequences (tuple, list) or dicts keyed by column position.
             Values are coerced to str, truncated to column width, left-justified.
    """
    headers = [col["header"] for col in columns]
    widths  = [col["width"]  for col in columns]

    header_line = " ".join(h.ljust(w) for h, w in zip(headers, widths))
    separator   = "-" * len(header_line)

    click.echo(header_line)
    click.echo(separator)
    for row in rows:
        vals = row if not isinstance(row, dict) else row.values()
        cells = [str(v or "")[:w].ljust(w) for v, w in zip(vals, widths)]
        click.echo(" ".join(cells))


def echo_load_stats(stats: dict) -> None:
    """Print the standard ETL load stats block to stdout."""
    click.echo(f"  Records read:      {stats.get('records_read', 0):>10,d}")
    click.echo(f"  Records inserted:  {stats.get('records_inserted', 0):>10,d}")
    click.echo(f"  Records updated:   {stats.get('records_updated', 0):>10,d}")
    click.echo(f"  Records skipped:   {stats.get('records_skipped', 0):>10,d}")
    click.echo(f"  Records errored:   {stats.get('records_errored', 0):>10,d}")


class QueryBuilder:
    """Accumulates SQL WHERE conditions and parameter values.

    Usage:
        qb = QueryBuilder()
        qb.filter("naics_code = %s", naics_code)
        qb.filter("agency_name LIKE %s", f"%{agency}%")
        where_sql, params = qb.build_where()
        cursor.execute(f"SELECT ... FROM ... {where_sql} LIMIT %s", params + [limit])
    """

    def __init__(self):
        self._clauses: list[str] = []
        self._params:  list     = []

    def filter(self, condition: str, *values) -> "QueryBuilder":
        """Add a condition only when all its values are truthy. Returns self for chaining."""
        if all(v is not None and v != "" for v in values):
            self._clauses.append(condition)
            self._params.extend(values)
        return self

    def build_where(self) -> tuple[str, list]:
        """Return (where_sql, params). where_sql is '' when no filters are active."""
        if not self._clauses:
            return "", []
        return "WHERE " + " AND ".join(self._clauses), list(self._params)
