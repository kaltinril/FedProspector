"""Schema drift checker - compares live MySQL database against DDL source files.

Parses the DDL SQL files in db/schema/ to extract expected schema, then queries
INFORMATION_SCHEMA on the live database to detect mismatches: missing tables,
missing columns, type differences, missing indexes, missing foreign keys, and
missing views.
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from config import settings
from db.connection import get_connection

logger = logging.getLogger("fed_prospector.schema_checker")

# ── Dataclasses for parsed schema ────────────────────────────────────────────

@dataclass
class ColumnDef:
    name: str
    col_type: str          # e.g. "VARCHAR(100)", "INT", "DECIMAL(15,2)"
    nullable: bool = True
    default: str | None = None
    extra: str = ""        # e.g. "AUTO_INCREMENT"


@dataclass
class IndexDef:
    name: str
    columns: list[str]
    unique: bool = False


@dataclass
class ForeignKeyDef:
    name: str
    columns: list[str]
    ref_table: str
    ref_columns: list[str]


@dataclass
class TableDef:
    name: str
    columns: list[ColumnDef] = field(default_factory=list)
    indexes: list[IndexDef] = field(default_factory=list)
    foreign_keys: list[ForeignKeyDef] = field(default_factory=list)
    primary_key: list[str] = field(default_factory=list)


@dataclass
class ViewDef:
    name: str
    definition: str = ""


@dataclass
class DriftItem:
    table: str
    category: str      # "missing_column", "extra_column", "type_mismatch", etc.
    detail: str
    fix_sql: str = ""


# ── Type normalization ───────────────────────────────────────────────────────

# Map MySQL display types to canonical form for comparison.
# MySQL 8.0+ no longer shows display widths (e.g., int(11) -> int),
# but DDL files may still have them.
_TYPE_ALIASES = {
    "INT":       "INT",
    "INTEGER":   "INT",
    "TINYINT":   "TINYINT",
    "SMALLINT":  "SMALLINT",
    "MEDIUMINT": "MEDIUMINT",
    "BIGINT":    "BIGINT",
    "BOOL":      "TINYINT",
    "BOOLEAN":   "TINYINT",
    "FLOAT":     "FLOAT",
    "DOUBLE":    "DOUBLE",
    "TEXT":      "TEXT",
    "MEDIUMTEXT":"MEDIUMTEXT",
    "LONGTEXT":  "LONGTEXT",
    "BLOB":      "BLOB",
    "JSON":      "JSON",
    "DATE":      "DATE",
    "DATETIME":  "DATETIME",
    "TIMESTAMP": "TIMESTAMP",
    "TIME":      "TIME",
}


def normalize_type(raw_type: str) -> str:
    """Normalize a column type string for comparison.

    Strips display widths from integer types, uppercases everything,
    and maps aliases to canonical forms.

    Examples:
        'int(11)'        -> 'INT'
        'varchar(100)'   -> 'VARCHAR(100)'
        'decimal(15,2)'  -> 'DECIMAL(15,2)'
        'bigint unsigned' -> 'BIGINT UNSIGNED'
    """
    t = raw_type.upper().strip()

    # Check for UNSIGNED suffix
    unsigned = ""
    if t.endswith(" UNSIGNED"):
        unsigned = " UNSIGNED"
        t = t[:-9].strip()

    # Extract base type and params
    m = re.match(r'^(\w+)(?:\(([^)]*)\))?(.*)$', t)
    if not m:
        return t + unsigned

    base = m.group(1)
    params = m.group(2)
    rest = m.group(3).strip()

    # Map aliases
    canonical = _TYPE_ALIASES.get(base, base)

    # For integer types, strip display width (MySQL 8.0 doesn't show them)
    if canonical in ("INT", "TINYINT", "SMALLINT", "MEDIUMINT", "BIGINT"):
        return canonical + unsigned

    # For types with params, preserve them
    if params:
        return f"{canonical}({params})" + unsigned

    return canonical + unsigned


# ── DDL parser ───────────────────────────────────────────────────────────────

def parse_ddl_files(schema_dir: Path) -> tuple[dict[str, TableDef], dict[str, ViewDef]]:
    """Parse all SQL files in schema_dir and return table/view definitions.

    Returns:
        (tables_dict, views_dict) keyed by lowercase name.
    """
    tables: dict[str, TableDef] = {}
    views: dict[str, ViewDef] = {}

    sql_files = []
    for subfolder in ["tables", "views", "functions", "procedures"]:
        sub_path = schema_dir / subfolder
        if sub_path.is_dir():
            sql_files.extend(sorted(sub_path.glob("*.sql")))

    if not sql_files:
        logger.warning("No SQL files found in %s", schema_dir)
        return tables, views

    for sql_file in sql_files:

        with open(sql_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Parse tables
        _parse_create_tables(content, tables)

        # Parse views
        _parse_create_views(content, views)

    return tables, views


def _parse_create_tables(sql: str, tables: dict[str, TableDef]):
    """Extract CREATE TABLE statements from SQL text."""
    # Match CREATE TABLE IF NOT EXISTS table_name ( ... ) ENGINE=...;
    pattern = re.compile(
        r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?`?(\w+)`?\s*\((.*?)\)\s*ENGINE',
        re.IGNORECASE | re.DOTALL,
    )

    for m in pattern.finditer(sql):
        table_name = m.group(1).lower()
        body = m.group(2)

        tdef = TableDef(name=table_name)
        _parse_table_body(body, tdef)
        tables[table_name] = tdef


def _parse_table_body(body: str, tdef: TableDef):
    """Parse the inside of a CREATE TABLE (...) block."""
    # Strip inline SQL comments before splitting (they can contain
    # parentheses and commas that confuse the depth-tracking splitter)
    body = re.sub(r'--[^\n]*', '', body)
    # Split on commas, but respect parentheses (for DECIMAL(15,2) etc.)
    lines = _split_table_body(body)

    for line in lines:
        line = line.strip()
        if not line:
            continue

        upper = line.upper().lstrip()

        # PRIMARY KEY
        if upper.startswith("PRIMARY KEY"):
            cols = _extract_paren_cols(line)
            tdef.primary_key = cols
            # Also add as an index (lowercase name to match INFORMATION_SCHEMA)
            tdef.indexes.append(IndexDef(name="primary", columns=cols, unique=True))
            continue

        # UNIQUE KEY / UNIQUE INDEX
        if upper.startswith("UNIQUE KEY") or upper.startswith("UNIQUE INDEX"):
            m = re.match(r'UNIQUE\s+(?:KEY|INDEX)\s+`?(\w+)`?\s*\((.+)\)', line, re.IGNORECASE)
            if m:
                name = m.group(1).lower()
                cols = _parse_index_columns(m.group(2))
                tdef.indexes.append(IndexDef(name=name, columns=cols, unique=True))
            continue

        # INDEX / KEY
        if upper.startswith("INDEX ") or (upper.startswith("KEY ") and not upper.startswith("KEY(")):
            m = re.match(r'(?:INDEX|KEY)\s+`?(\w+)`?\s*\((.+)\)', line, re.IGNORECASE)
            if m:
                name = m.group(1).lower()
                cols = _parse_index_columns(m.group(2))
                tdef.indexes.append(IndexDef(name=name, columns=cols))
            continue

        # CONSTRAINT ... FOREIGN KEY
        if upper.startswith("CONSTRAINT") and "FOREIGN KEY" in upper:
            m = re.match(
                r'CONSTRAINT\s+`?(\w+)`?\s+FOREIGN\s+KEY\s*\((.+?)\)\s*REFERENCES\s+`?(\w+)`?\s*\((.+?)\)',
                line, re.IGNORECASE,
            )
            if m:
                fk_name = m.group(1).lower()
                fk_cols = _parse_index_columns(m.group(2))
                ref_table = m.group(3).lower()
                ref_cols = _parse_index_columns(m.group(4))
                tdef.foreign_keys.append(
                    ForeignKeyDef(name=fk_name, columns=fk_cols,
                                  ref_table=ref_table, ref_columns=ref_cols)
                )
            continue

        # Column definition
        col = _parse_column_line(line)
        if col:
            tdef.columns.append(col)
            # If column has inline PRIMARY KEY, record it
            if re.search(r'\bPRIMARY\s+KEY\b', line, re.IGNORECASE):
                tdef.primary_key = [col.name]
                tdef.indexes.append(IndexDef(name="primary", columns=[col.name], unique=True))


def _split_table_body(body: str) -> list[str]:
    """Split CREATE TABLE body on commas, respecting parenthesized groups."""
    parts = []
    depth = 0
    current = []

    for char in body:
        if char == '(':
            depth += 1
            current.append(char)
        elif char == ')':
            depth -= 1
            current.append(char)
        elif char == ',' and depth == 0:
            parts.append(''.join(current))
            current = []
        else:
            current.append(char)

    if current:
        parts.append(''.join(current))

    return parts


def _extract_paren_cols(line: str) -> list[str]:
    """Extract column names from e.g. 'PRIMARY KEY (col1, col2)'."""
    m = re.search(r'\((.+?)\)', line)
    if m:
        return _parse_index_columns(m.group(1))
    return []


def _parse_index_columns(cols_str: str) -> list[str]:
    """Parse 'col1, col2(50)' -> ['col1', 'col2'].

    Splits on commas respecting parentheses (for prefix lengths).
    """
    cols = []
    # Use the paren-aware splitter to handle col_name(50) correctly
    parts = _split_table_body(cols_str)
    for part in parts:
        part = part.strip().strip('`')
        # Strip prefix length like (50)
        name = re.sub(r'\(\d+\)', '', part).strip()
        if name:
            cols.append(name.lower())
    return cols


def _parse_column_line(line: str) -> ColumnDef | None:
    """Parse a single column definition line.

    Examples:
        'uei_sam VARCHAR(12) NOT NULL'
        'id INT AUTO_INCREMENT PRIMARY KEY'
        'created_at DATETIME DEFAULT CURRENT_TIMESTAMP'
    """
    line = line.strip()

    # Skip lines that start with keywords (not column defs).
    # Use regex word boundary to avoid matching column names like primary_naics.
    upper = line.upper()
    if re.match(r'^(PRIMARY\s+KEY|INDEX\s|KEY\s|UNIQUE\s|CONSTRAINT\s|FOREIGN\s|CHECK\s|ENGINE\s)', upper):
        return None

    # Match: column_name TYPE [rest...]
    # Column name may be backtick-quoted
    m = re.match(r'^`?(\w+)`?\s+(.+)$', line, re.IGNORECASE)
    if not m:
        return None

    name = m.group(1).lower()
    rest = m.group(2).strip()

    # Skip if "name" is a SQL keyword that sneaked in
    if name.upper() in ("PRIMARY", "INDEX", "KEY", "UNIQUE", "CONSTRAINT",
                         "FOREIGN", "CHECK", "ENGINE"):
        return None

    # Extract type: everything up to the first keyword or end
    type_match = re.match(
        r'^(\w+(?:\([^)]*\))?(?:\s+UNSIGNED)?)',
        rest, re.IGNORECASE,
    )
    if not type_match:
        return None

    col_type = normalize_type(type_match.group(1))

    # Determine nullable
    nullable = True
    if re.search(r'\bNOT\s+NULL\b', rest, re.IGNORECASE):
        nullable = False
    # PRIMARY KEY implies NOT NULL
    if re.search(r'\bPRIMARY\s+KEY\b', rest, re.IGNORECASE):
        nullable = False

    # Detect AUTO_INCREMENT
    extra = ""
    if re.search(r'\bAUTO_INCREMENT\b', rest, re.IGNORECASE):
        extra = "auto_increment"

    # Detect DEFAULT
    default = None
    dm = re.search(r"\bDEFAULT\s+('(?:[^']*)'|[\w()]+(?:\s+ON\s+UPDATE\s+\w+)?)", rest, re.IGNORECASE)
    if dm:
        default = dm.group(1).strip("'")

    return ColumnDef(
        name=name,
        col_type=col_type,
        nullable=nullable,
        default=default,
        extra=extra,
    )


def _parse_create_views(sql: str, views: dict[str, ViewDef]):
    """Extract CREATE OR REPLACE VIEW definitions."""
    pattern = re.compile(
        r'CREATE\s+OR\s+REPLACE\s+VIEW\s+`?(\w+)`?\s+AS\s+',
        re.IGNORECASE,
    )
    for m in pattern.finditer(sql):
        view_name = m.group(1).lower()
        views[view_name] = ViewDef(name=view_name)


# ── Live database introspection ──────────────────────────────────────────────

def get_live_tables(cursor) -> dict[str, TableDef]:
    """Query INFORMATION_SCHEMA to get all tables in the database."""
    db_name = settings.DB_NAME
    tables: dict[str, TableDef] = {}

    # Get table list (base tables only)
    cursor.execute(
        "SELECT TABLE_NAME FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'BASE TABLE'",
        (db_name,),
    )
    for (table_name,) in cursor.fetchall():
        tables[table_name.lower()] = TableDef(name=table_name.lower())

    # Get columns
    cursor.execute(
        "SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, "
        "COLUMN_DEFAULT, EXTRA "
        "FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = %s "
        "ORDER BY TABLE_NAME, ORDINAL_POSITION",
        (db_name,),
    )
    for table_name, col_name, col_type, is_nullable, col_default, extra in cursor.fetchall():
        tname = table_name.lower()
        if tname not in tables:
            continue
        tables[tname].columns.append(ColumnDef(
            name=col_name.lower(),
            col_type=normalize_type(col_type),
            nullable=(is_nullable == "YES"),
            default=col_default,
            extra=extra.lower() if extra else "",
        ))

    # Get indexes
    cursor.execute(
        "SELECT TABLE_NAME, INDEX_NAME, COLUMN_NAME, NON_UNIQUE, SEQ_IN_INDEX "
        "FROM information_schema.STATISTICS "
        "WHERE TABLE_SCHEMA = %s "
        "ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX",
        (db_name,),
    )
    # Aggregate columns per index
    idx_map: dict[tuple[str, str], tuple[list[str], bool]] = {}
    for table_name, idx_name, col_name, non_unique, seq in cursor.fetchall():
        key = (table_name.lower(), idx_name.lower())
        if key not in idx_map:
            idx_map[key] = ([], non_unique == 0)
        idx_map[key][0].append(col_name.lower())

    for (tname, idx_name), (cols, is_unique) in idx_map.items():
        if tname in tables:
            tables[tname].indexes.append(
                IndexDef(name=idx_name, columns=cols, unique=is_unique)
            )

    # Get foreign keys
    cursor.execute(
        "SELECT CONSTRAINT_NAME, TABLE_NAME, COLUMN_NAME, "
        "REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME "
        "FROM information_schema.KEY_COLUMN_USAGE "
        "WHERE TABLE_SCHEMA = %s AND REFERENCED_TABLE_NAME IS NOT NULL "
        "ORDER BY CONSTRAINT_NAME, ORDINAL_POSITION",
        (db_name,),
    )
    fk_map: dict[tuple[str, str], tuple[list[str], str, list[str]]] = {}
    for fk_name, table_name, col_name, ref_table, ref_col in cursor.fetchall():
        key = (table_name.lower(), fk_name.lower())
        if key not in fk_map:
            fk_map[key] = ([], ref_table.lower(), [])
        fk_map[key][0].append(col_name.lower())
        fk_map[key][2].append(ref_col.lower())

    for (tname, fk_name), (cols, ref_table, ref_cols) in fk_map.items():
        if tname in tables:
            tables[tname].foreign_keys.append(
                ForeignKeyDef(name=fk_name, columns=cols,
                              ref_table=ref_table, ref_columns=ref_cols)
            )

    return tables


def get_live_views(cursor) -> dict[str, ViewDef]:
    """Query INFORMATION_SCHEMA to get all views in the database."""
    views: dict[str, ViewDef] = {}
    cursor.execute(
        "SELECT TABLE_NAME FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'VIEW'",
        (settings.DB_NAME,),
    )
    for (view_name,) in cursor.fetchall():
        views[view_name.lower()] = ViewDef(name=view_name.lower())
    return views


# ── Comparison logic ─────────────────────────────────────────────────────────

def compare_schemas(
    expected_tables: dict[str, TableDef],
    live_tables: dict[str, TableDef],
    expected_views: dict[str, ViewDef],
    live_views: dict[str, ViewDef],
    table_filter: str | None = None,
) -> list[DriftItem]:
    """Compare expected (DDL) vs live (DB) schemas and return drift items."""
    drifts: list[DriftItem] = []

    # Optionally filter to a single table
    if table_filter:
        tf = table_filter.lower()
        check_tables = {tf: expected_tables[tf]} if tf in expected_tables else {}
        if not check_tables:
            drifts.append(DriftItem(
                table=tf, category="not_in_ddl",
                detail=f"Table '{tf}' not found in DDL files",
            ))
            return drifts
    else:
        check_tables = expected_tables

    # Tables in DDL but missing from DB
    for tname in sorted(check_tables):
        if tname not in live_tables:
            drifts.append(DriftItem(
                table=tname, category="missing_table",
                detail=f"Table '{tname}' is defined in DDL but missing from database",
            ))
            continue

        # Compare columns
        drifts.extend(_compare_columns(tname, check_tables[tname], live_tables[tname]))

        # Compare indexes
        drifts.extend(_compare_indexes(tname, check_tables[tname], live_tables[tname]))

        # Compare foreign keys
        drifts.extend(_compare_foreign_keys(tname, check_tables[tname], live_tables[tname]))

    # Tables in DB but missing from DDL (only when not filtering)
    if not table_filter:
        for tname in sorted(live_tables):
            if tname not in expected_tables:
                drifts.append(DriftItem(
                    table=tname, category="extra_table",
                    detail=f"Table '{tname}' exists in database but not in DDL files",
                ))

        # Views in DDL but missing from DB
        for vname in sorted(expected_views):
            if vname not in live_views:
                drifts.append(DriftItem(
                    table=vname, category="missing_view",
                    detail=f"View '{vname}' is defined in DDL but missing from database",
                ))

        # Views in DB but missing from DDL
        for vname in sorted(live_views):
            if vname not in expected_views:
                drifts.append(DriftItem(
                    table=vname, category="extra_view",
                    detail=f"View '{vname}' exists in database but not in DDL files",
                ))

    return drifts


def _compare_columns(table: str, expected: TableDef, live: TableDef) -> list[DriftItem]:
    """Compare columns between expected and live table definitions."""
    drifts = []

    expected_cols = {c.name: c for c in expected.columns}
    live_cols = {c.name: c for c in live.columns}

    # Columns in DDL but missing from DB
    for cname in sorted(expected_cols):
        if cname not in live_cols:
            ecol = expected_cols[cname]
            null_str = "" if ecol.nullable else " NOT NULL"
            default_str = f" DEFAULT {ecol.default}" if ecol.default else ""
            extra_str = f" {ecol.extra.upper()}" if ecol.extra else ""
            drifts.append(DriftItem(
                table=table, category="missing_column",
                detail=f"Missing column: {cname} {ecol.col_type}{null_str}",
                fix_sql=f"ALTER TABLE `{table}` ADD COLUMN `{cname}` {ecol.col_type}{null_str}{default_str}{extra_str};",
            ))
            continue

        # Type mismatch
        ecol = expected_cols[cname]
        lcol = live_cols[cname]
        if ecol.col_type != lcol.col_type:
            drifts.append(DriftItem(
                table=table, category="type_mismatch",
                detail=f"Type mismatch: {cname} — DDL: {ecol.col_type}, DB: {lcol.col_type}",
                fix_sql=f"ALTER TABLE `{table}` MODIFY COLUMN `{cname}` {ecol.col_type};",
            ))

    # Columns in DB but missing from DDL
    for cname in sorted(live_cols):
        if cname not in expected_cols:
            lcol = live_cols[cname]
            drifts.append(DriftItem(
                table=table, category="extra_column",
                detail=f"Extra column: {cname} {lcol.col_type} (in DB but not in DDL)",
            ))

    return drifts


def _compare_indexes(table: str, expected: TableDef, live: TableDef) -> list[DriftItem]:
    """Compare indexes between expected and live table definitions."""
    drifts = []

    # Build lookup by index name
    live_idx = {i.name: i for i in live.indexes}

    for eidx in expected.indexes:
        if eidx.name not in live_idx:
            cols = ", ".join(f"`{c}`" for c in eidx.columns)
            unique_kw = "UNIQUE " if eidx.unique and eidx.name != "PRIMARY" else ""
            if eidx.name == "PRIMARY":
                fix = f"ALTER TABLE `{table}` ADD PRIMARY KEY ({cols});"
            else:
                fix = f"ALTER TABLE `{table}` ADD {unique_kw}INDEX `{eidx.name}` ({cols});"
            drifts.append(DriftItem(
                table=table, category="missing_index",
                detail=f"Missing index: {eidx.name} ({', '.join(eidx.columns)})",
                fix_sql=fix,
            ))
        else:
            # Check if columns match
            lidx = live_idx[eidx.name]
            if eidx.columns != lidx.columns:
                drifts.append(DriftItem(
                    table=table, category="index_mismatch",
                    detail=f"Index column mismatch: {eidx.name} — DDL: {eidx.columns}, DB: {lidx.columns}",
                ))

    return drifts


def _compare_foreign_keys(table: str, expected: TableDef, live: TableDef) -> list[DriftItem]:
    """Compare foreign keys between expected and live table definitions."""
    drifts = []

    live_fks = {fk.name: fk for fk in live.foreign_keys}

    for efk in expected.foreign_keys:
        if efk.name not in live_fks:
            cols = ", ".join(f"`{c}`" for c in efk.columns)
            ref_cols = ", ".join(f"`{c}`" for c in efk.ref_columns)
            fix = (
                f"ALTER TABLE `{table}` ADD CONSTRAINT `{efk.name}` "
                f"FOREIGN KEY ({cols}) REFERENCES `{efk.ref_table}` ({ref_cols});"
            )
            drifts.append(DriftItem(
                table=table, category="missing_fk",
                detail=f"Missing FK: {efk.name} ({', '.join(efk.columns)}) -> {efk.ref_table}({', '.join(efk.ref_columns)})",
                fix_sql=fix,
            ))

    return drifts


# ── Main check function ─────────────────────────────────────────────────────

def run_schema_check(
    table_filter: str | None = None,
) -> tuple[dict[str, TableDef], dict[str, ViewDef],
           dict[str, TableDef], dict[str, ViewDef],
           list[DriftItem]]:
    """Run the full schema drift check.

    Returns:
        (expected_tables, expected_views, live_tables, live_views, drifts)
    """
    schema_dir = Path(__file__).parent.parent / "db" / "schema"

    # Parse DDL files
    expected_tables, expected_views = parse_ddl_files(schema_dir)
    logger.info("Parsed DDL: %d tables, %d views", len(expected_tables), len(expected_views))

    # Query live database
    conn = get_connection()
    cursor = conn.cursor()
    try:
        live_tables = get_live_tables(cursor)
        live_views = get_live_views(cursor)
        logger.info("Live DB: %d tables, %d views", len(live_tables), len(live_views))
    finally:
        cursor.close()
        conn.close()

    # Compare
    drifts = compare_schemas(expected_tables, live_tables,
                             expected_views, live_views, table_filter)

    return expected_tables, expected_views, live_tables, live_views, drifts
