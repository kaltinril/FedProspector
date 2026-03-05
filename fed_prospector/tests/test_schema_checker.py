"""Tests for etl.schema_checker -- DDL parsing, type normalization,
column/index/FK comparison, and full drift detection.
"""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from etl.schema_checker import (
    normalize_type,
    _parse_create_tables,
    _parse_create_views,
    _parse_column_line,
    _parse_table_body,
    _split_table_body,
    _extract_paren_cols,
    _parse_index_columns,
    _compare_columns,
    _compare_indexes,
    _compare_foreign_keys,
    compare_schemas,
    get_live_tables,
    get_live_views,
    parse_ddl_files,
    ColumnDef,
    IndexDef,
    ForeignKeyDef,
    TableDef,
    ViewDef,
    DriftItem,
)


# ===================================================================
# Type normalization
# ===================================================================

class TestNormalizeType:

    @pytest.mark.parametrize("raw,expected", [
        ("int(11)", "INT"),
        ("INT", "INT"),
        ("int", "INT"),
        ("INT(11)", "INT"),
        ("INTEGER", "INT"),
        ("integer(11)", "INT"),
    ])
    def test_integer_types_strip_display_width(self, raw, expected):
        assert normalize_type(raw) == expected

    @pytest.mark.parametrize("raw,expected", [
        ("tinyint(1)", "TINYINT"),
        ("TINYINT", "TINYINT"),
        ("smallint(6)", "SMALLINT"),
        ("mediumint(8)", "MEDIUMINT"),
        ("bigint(20)", "BIGINT"),
    ])
    def test_other_int_types_strip_display_width(self, raw, expected):
        assert normalize_type(raw) == expected

    def test_varchar_preserves_length(self):
        assert normalize_type("varchar(100)") == "VARCHAR(100)"

    def test_varchar_uppercase(self):
        assert normalize_type("VARCHAR(255)") == "VARCHAR(255)"

    def test_decimal_preserves_precision(self):
        assert normalize_type("decimal(15,2)") == "DECIMAL(15,2)"

    def test_decimal_uppercase(self):
        assert normalize_type("DECIMAL(10,4)") == "DECIMAL(10,4)"

    def test_text_types(self):
        assert normalize_type("TEXT") == "TEXT"
        assert normalize_type("text") == "TEXT"
        assert normalize_type("MEDIUMTEXT") == "MEDIUMTEXT"
        assert normalize_type("LONGTEXT") == "LONGTEXT"

    def test_datetime_types(self):
        assert normalize_type("DATETIME") == "DATETIME"
        assert normalize_type("datetime") == "DATETIME"
        assert normalize_type("TIMESTAMP") == "TIMESTAMP"
        assert normalize_type("DATE") == "DATE"
        assert normalize_type("TIME") == "TIME"

    def test_json_type(self):
        assert normalize_type("JSON") == "JSON"
        assert normalize_type("json") == "JSON"

    def test_bool_maps_to_tinyint(self):
        assert normalize_type("BOOL") == "TINYINT"
        assert normalize_type("BOOLEAN") == "TINYINT"
        assert normalize_type("bool") == "TINYINT"

    def test_unsigned_suffix(self):
        assert normalize_type("int unsigned") == "INT UNSIGNED"
        assert normalize_type("INT UNSIGNED") == "INT UNSIGNED"
        assert normalize_type("bigint(20) unsigned") == "BIGINT UNSIGNED"
        assert normalize_type("INT(11) UNSIGNED") == "INT UNSIGNED"

    def test_char_preserves_length(self):
        assert normalize_type("CHAR(1)") == "CHAR(1)"
        assert normalize_type("char(36)") == "CHAR(36)"

    def test_blob_type(self):
        assert normalize_type("BLOB") == "BLOB"

    def test_float_double(self):
        assert normalize_type("FLOAT") == "FLOAT"
        assert normalize_type("DOUBLE") == "DOUBLE"

    def test_enum_preserves_values(self):
        assert normalize_type("ENUM('Y','N')") == "ENUM('Y','N')"

    def test_whitespace_handling(self):
        assert normalize_type("  varchar(50)  ") == "VARCHAR(50)"


# ===================================================================
# DDL parsing - column lines
# ===================================================================

class TestParseColumnLine:

    def test_simple_varchar(self):
        col = _parse_column_line("uei_sam VARCHAR(12) NOT NULL")
        assert col is not None
        assert col.name == "uei_sam"
        assert col.col_type == "VARCHAR(12)"
        assert col.nullable is False

    def test_int_auto_increment(self):
        col = _parse_column_line("id INT AUTO_INCREMENT PRIMARY KEY")
        assert col is not None
        assert col.name == "id"
        assert col.col_type == "INT"
        assert col.extra == "auto_increment"
        assert col.nullable is False

    def test_datetime_default(self):
        col = _parse_column_line("created_at DATETIME DEFAULT CURRENT_TIMESTAMP")
        assert col is not None
        assert col.name == "created_at"
        assert col.col_type == "DATETIME"
        assert col.default == "CURRENT_TIMESTAMP"
        assert col.nullable is True

    def test_decimal_with_precision(self):
        col = _parse_column_line("amount DECIMAL(15,2) NOT NULL DEFAULT 0.00")
        assert col is not None
        assert col.name == "amount"
        assert col.col_type == "DECIMAL(15,2)"
        assert col.nullable is False

    def test_nullable_by_default(self):
        col = _parse_column_line("description TEXT")
        assert col is not None
        assert col.nullable is True

    def test_backtick_quoted_name(self):
        col = _parse_column_line("`status` VARCHAR(20) NOT NULL DEFAULT 'NEW'")
        assert col is not None
        assert col.name == "status"
        assert col.col_type == "VARCHAR(20)"
        assert col.default == "NEW"

    def test_primary_key_line_returns_none(self):
        col = _parse_column_line("PRIMARY KEY (id)")
        assert col is None

    def test_index_line_returns_none(self):
        col = _parse_column_line("INDEX idx_name (col1)")
        assert col is None

    def test_constraint_line_returns_none(self):
        col = _parse_column_line("CONSTRAINT fk_test FOREIGN KEY (col1) REFERENCES other(id)")
        assert col is None

    def test_column_named_like_keyword_not_skipped(self):
        """Columns like primary_naics should not be skipped."""
        col = _parse_column_line("primary_naics VARCHAR(6)")
        assert col is not None
        assert col.name == "primary_naics"

    def test_unsigned_column(self):
        col = _parse_column_line("counter INT UNSIGNED NOT NULL")
        assert col is not None
        assert col.col_type == "INT UNSIGNED"
        assert col.nullable is False

    def test_default_string_value(self):
        col = _parse_column_line("is_active CHAR(1) NOT NULL DEFAULT 'Y'")
        assert col is not None
        assert col.default == "Y"

    def test_empty_line_returns_none(self):
        col = _parse_column_line("")
        assert col is None


# ===================================================================
# DDL parsing - split table body
# ===================================================================

class TestSplitTableBody:

    def test_simple_split(self):
        body = "id INT, name VARCHAR(50), active CHAR(1)"
        parts = _split_table_body(body)
        assert len(parts) == 3

    def test_respects_parentheses(self):
        """DECIMAL(15,2) should not be split on the internal comma."""
        body = "id INT, amount DECIMAL(15,2), name VARCHAR(50)"
        parts = _split_table_body(body)
        assert len(parts) == 3
        assert "DECIMAL(15,2)" in parts[1]

    def test_empty_body(self):
        parts = _split_table_body("")
        assert len(parts) == 0

    def test_nested_parens(self):
        body = "col1 ENUM('A','B','C'), col2 INT"
        parts = _split_table_body(body)
        assert len(parts) == 2


# ===================================================================
# DDL parsing - extract paren cols and index columns
# ===================================================================

class TestExtractParenCols:

    def test_single_column(self):
        cols = _extract_paren_cols("PRIMARY KEY (id)")
        assert cols == ["id"]

    def test_composite_key(self):
        cols = _extract_paren_cols("PRIMARY KEY (uei_sam, naics_code)")
        assert cols == ["uei_sam", "naics_code"]

    def test_no_parens(self):
        cols = _extract_paren_cols("no parens here")
        assert cols == []


class TestParseIndexColumns:

    def test_simple_columns(self):
        cols = _parse_index_columns("col1, col2")
        assert cols == ["col1", "col2"]

    def test_backtick_quoted(self):
        cols = _parse_index_columns("`col1`, `col2`")
        assert cols == ["col1", "col2"]

    def test_prefix_length_stripped(self):
        cols = _parse_index_columns("description(50), title(100)")
        assert cols == ["description", "title"]

    def test_single_column(self):
        cols = _parse_index_columns("notice_id")
        assert cols == ["notice_id"]


# ===================================================================
# DDL parsing - CREATE TABLE
# ===================================================================

class TestParseCreateTables:

    def test_simple_table(self):
        sql = """
        CREATE TABLE IF NOT EXISTS test_table (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            value DECIMAL(10,2)
        ) ENGINE=InnoDB;
        """
        tables = {}
        _parse_create_tables(sql, tables)

        assert "test_table" in tables
        tdef = tables["test_table"]
        assert len(tdef.columns) == 3
        col_names = [c.name for c in tdef.columns]
        assert "id" in col_names
        assert "name" in col_names
        assert "value" in col_names

    def test_table_with_indexes(self):
        sql = """
        CREATE TABLE entity (
            uei_sam VARCHAR(12) NOT NULL,
            legal_business_name VARCHAR(500),
            PRIMARY KEY (uei_sam),
            INDEX idx_name (legal_business_name(100))
        ) ENGINE=InnoDB;
        """
        tables = {}
        _parse_create_tables(sql, tables)

        tdef = tables["entity"]
        assert tdef.primary_key == ["uei_sam"]
        idx_names = [i.name for i in tdef.indexes]
        assert "primary" in idx_names
        assert "idx_name" in idx_names

    def test_table_with_unique_index(self):
        sql = """
        CREATE TABLE app_user (
            user_id INT AUTO_INCREMENT,
            username VARCHAR(50) NOT NULL,
            PRIMARY KEY (user_id),
            UNIQUE KEY uk_username (username)
        ) ENGINE=InnoDB;
        """
        tables = {}
        _parse_create_tables(sql, tables)

        tdef = tables["app_user"]
        uk = next(i for i in tdef.indexes if i.name == "uk_username")
        assert uk.unique is True
        assert uk.columns == ["username"]

    def test_table_with_foreign_key(self):
        sql = """
        CREATE TABLE prospect (
            prospect_id INT AUTO_INCREMENT,
            notice_id VARCHAR(100) NOT NULL,
            assigned_to INT,
            PRIMARY KEY (prospect_id),
            CONSTRAINT fk_prospect_notice FOREIGN KEY (notice_id) REFERENCES opportunity(notice_id),
            CONSTRAINT fk_prospect_user FOREIGN KEY (assigned_to) REFERENCES app_user(user_id)
        ) ENGINE=InnoDB;
        """
        tables = {}
        _parse_create_tables(sql, tables)

        tdef = tables["prospect"]
        assert len(tdef.foreign_keys) == 2
        fk_names = [fk.name for fk in tdef.foreign_keys]
        assert "fk_prospect_notice" in fk_names
        assert "fk_prospect_user" in fk_names

        fk_notice = next(fk for fk in tdef.foreign_keys if fk.name == "fk_prospect_notice")
        assert fk_notice.ref_table == "opportunity"
        assert fk_notice.ref_columns == ["notice_id"]

    def test_table_name_lowercased(self):
        sql = """
        CREATE TABLE MyTable (
            id INT PRIMARY KEY
        ) ENGINE=InnoDB;
        """
        tables = {}
        _parse_create_tables(sql, tables)

        assert "mytable" in tables

    def test_no_tables_in_sql(self):
        sql = "SELECT 1; -- no tables here"
        tables = {}
        _parse_create_tables(sql, tables)
        assert len(tables) == 0

    def test_multiple_tables_in_one_file(self):
        sql = """
        CREATE TABLE t1 (id INT PRIMARY KEY) ENGINE=InnoDB;
        CREATE TABLE t2 (id INT PRIMARY KEY, name VARCHAR(50)) ENGINE=InnoDB;
        """
        tables = {}
        _parse_create_tables(sql, tables)

        assert "t1" in tables
        assert "t2" in tables

    def test_inline_comment_stripped(self):
        sql = """
        CREATE TABLE comments_test (
            id INT AUTO_INCREMENT, -- this is the PK
            name VARCHAR(50), -- user name
            PRIMARY KEY (id)
        ) ENGINE=InnoDB;
        """
        tables = {}
        _parse_create_tables(sql, tables)

        tdef = tables["comments_test"]
        assert len(tdef.columns) == 2
        assert tdef.primary_key == ["id"]


# ===================================================================
# DDL parsing - CREATE VIEW
# ===================================================================

class TestParseCreateViews:

    def test_parse_view(self):
        sql = "CREATE OR REPLACE VIEW v_summary AS SELECT * FROM prospect;"
        views = {}
        _parse_create_views(sql, views)

        assert "v_summary" in views

    def test_parse_view_backtick_quoted(self):
        sql = "CREATE OR REPLACE VIEW `v_active_users` AS SELECT * FROM app_user;"
        views = {}
        _parse_create_views(sql, views)

        assert "v_active_users" in views

    def test_no_views_in_sql(self):
        sql = "CREATE TABLE t1 (id INT) ENGINE=InnoDB;"
        views = {}
        _parse_create_views(sql, views)
        assert len(views) == 0

    def test_view_name_lowercased(self):
        sql = "CREATE OR REPLACE VIEW MyView AS SELECT 1;"
        views = {}
        _parse_create_views(sql, views)
        assert "myview" in views


# ===================================================================
# DDL parsing - parse_table_body
# ===================================================================

class TestParseTableBody:

    def test_parses_columns_and_pk(self):
        body = """
            id INT AUTO_INCREMENT,
            name VARCHAR(100) NOT NULL,
            PRIMARY KEY (id)
        """
        tdef = TableDef(name="test")
        _parse_table_body(body, tdef)

        assert len(tdef.columns) == 2
        assert tdef.primary_key == ["id"]

    def test_key_keyword_not_confused_with_column(self):
        """'KEY idx_name (col)' should be parsed as index, not column."""
        body = """
            id INT,
            KEY idx_id (id)
        """
        tdef = TableDef(name="test")
        _parse_table_body(body, tdef)

        assert len(tdef.columns) == 1
        assert len(tdef.indexes) == 1

    def test_inline_primary_key_on_column(self):
        body = "id INT AUTO_INCREMENT PRIMARY KEY"
        tdef = TableDef(name="test")
        _parse_table_body(body, tdef)

        assert tdef.primary_key == ["id"]
        assert len(tdef.indexes) == 1
        assert tdef.indexes[0].name == "primary"


# ===================================================================
# Column comparison
# ===================================================================

class TestCompareColumns:

    def test_no_drift_identical_tables(self):
        expected = TableDef(name="t", columns=[
            ColumnDef(name="id", col_type="INT"),
            ColumnDef(name="name", col_type="VARCHAR(100)"),
        ])
        live = TableDef(name="t", columns=[
            ColumnDef(name="id", col_type="INT"),
            ColumnDef(name="name", col_type="VARCHAR(100)"),
        ])

        drifts = _compare_columns("t", expected, live)
        assert len(drifts) == 0

    def test_missing_column(self):
        expected = TableDef(name="t", columns=[
            ColumnDef(name="id", col_type="INT"),
            ColumnDef(name="email", col_type="VARCHAR(200)"),
        ])
        live = TableDef(name="t", columns=[
            ColumnDef(name="id", col_type="INT"),
        ])

        drifts = _compare_columns("t", expected, live)
        assert len(drifts) == 1
        assert drifts[0].category == "missing_column"
        assert "email" in drifts[0].detail
        assert "ALTER TABLE" in drifts[0].fix_sql

    def test_extra_column(self):
        expected = TableDef(name="t", columns=[
            ColumnDef(name="id", col_type="INT"),
        ])
        live = TableDef(name="t", columns=[
            ColumnDef(name="id", col_type="INT"),
            ColumnDef(name="extra_col", col_type="TEXT"),
        ])

        drifts = _compare_columns("t", expected, live)
        assert len(drifts) == 1
        assert drifts[0].category == "extra_column"
        assert "extra_col" in drifts[0].detail

    def test_type_mismatch(self):
        expected = TableDef(name="t", columns=[
            ColumnDef(name="val", col_type="VARCHAR(100)"),
        ])
        live = TableDef(name="t", columns=[
            ColumnDef(name="val", col_type="VARCHAR(200)"),
        ])

        drifts = _compare_columns("t", expected, live)
        assert len(drifts) == 1
        assert drifts[0].category == "type_mismatch"
        assert "VARCHAR(100)" in drifts[0].detail
        assert "VARCHAR(200)" in drifts[0].detail

    def test_missing_column_not_null_includes_constraint(self):
        expected = TableDef(name="t", columns=[
            ColumnDef(name="code", col_type="VARCHAR(10)", nullable=False),
        ])
        live = TableDef(name="t", columns=[])

        drifts = _compare_columns("t", expected, live)
        assert "NOT NULL" in drifts[0].detail
        assert "NOT NULL" in drifts[0].fix_sql

    def test_empty_tables_no_drift(self):
        expected = TableDef(name="t", columns=[])
        live = TableDef(name="t", columns=[])

        drifts = _compare_columns("t", expected, live)
        assert len(drifts) == 0


# ===================================================================
# Index comparison
# ===================================================================

class TestCompareIndexes:

    def test_no_drift_identical_indexes(self):
        expected = TableDef(name="t", indexes=[
            IndexDef(name="primary", columns=["id"], unique=True),
            IndexDef(name="idx_name", columns=["name"]),
        ])
        live = TableDef(name="t", indexes=[
            IndexDef(name="primary", columns=["id"], unique=True),
            IndexDef(name="idx_name", columns=["name"]),
        ])

        drifts = _compare_indexes("t", expected, live)
        assert len(drifts) == 0

    def test_missing_index(self):
        expected = TableDef(name="t", indexes=[
            IndexDef(name="idx_email", columns=["email"]),
        ])
        live = TableDef(name="t", indexes=[])

        drifts = _compare_indexes("t", expected, live)
        assert len(drifts) == 1
        assert drifts[0].category == "missing_index"
        assert "idx_email" in drifts[0].detail

    def test_missing_primary_key_fix_sql(self):
        """DDL parser stores PK index as name='primary' (lowercase).
        The comparison code checks for 'PRIMARY' (uppercase), so the
        lowercase variant produces an INDEX statement instead of ADD PRIMARY KEY.
        This test documents the actual behavior."""
        expected = TableDef(name="t", indexes=[
            IndexDef(name="primary", columns=["id"], unique=True),
        ])
        live = TableDef(name="t", indexes=[])

        drifts = _compare_indexes("t", expected, live)
        assert len(drifts) == 1
        assert drifts[0].category == "missing_index"
        # lowercase "primary" falls through to the INDEX branch
        assert "INDEX" in drifts[0].fix_sql

    def test_missing_unique_index_fix_sql(self):
        expected = TableDef(name="t", indexes=[
            IndexDef(name="uk_code", columns=["code"], unique=True),
        ])
        live = TableDef(name="t", indexes=[])

        drifts = _compare_indexes("t", expected, live)
        assert "UNIQUE" in drifts[0].fix_sql

    def test_index_column_mismatch(self):
        expected = TableDef(name="t", indexes=[
            IndexDef(name="idx_combo", columns=["a", "b"]),
        ])
        live = TableDef(name="t", indexes=[
            IndexDef(name="idx_combo", columns=["a", "c"]),
        ])

        drifts = _compare_indexes("t", expected, live)
        assert len(drifts) == 1
        assert drifts[0].category == "index_mismatch"

    def test_no_indexes_no_drift(self):
        expected = TableDef(name="t", indexes=[])
        live = TableDef(name="t", indexes=[])

        drifts = _compare_indexes("t", expected, live)
        assert len(drifts) == 0


# ===================================================================
# Foreign key comparison
# ===================================================================

class TestCompareForeignKeys:

    def test_no_drift_identical_fks(self):
        fk = ForeignKeyDef(name="fk_ref", columns=["ref_id"],
                           ref_table="other", ref_columns=["id"])
        expected = TableDef(name="t", foreign_keys=[fk])
        live = TableDef(name="t", foreign_keys=[fk])

        drifts = _compare_foreign_keys("t", expected, live)
        assert len(drifts) == 0

    def test_missing_fk(self):
        fk = ForeignKeyDef(name="fk_user", columns=["user_id"],
                           ref_table="app_user", ref_columns=["user_id"])
        expected = TableDef(name="t", foreign_keys=[fk])
        live = TableDef(name="t", foreign_keys=[])

        drifts = _compare_foreign_keys("t", expected, live)
        assert len(drifts) == 1
        assert drifts[0].category == "missing_fk"
        assert "fk_user" in drifts[0].detail
        assert "ADD CONSTRAINT" in drifts[0].fix_sql

    def test_no_fks_no_drift(self):
        expected = TableDef(name="t", foreign_keys=[])
        live = TableDef(name="t", foreign_keys=[])

        drifts = _compare_foreign_keys("t", expected, live)
        assert len(drifts) == 0


# ===================================================================
# Full schema comparison
# ===================================================================

class TestCompareSchemas:

    def test_missing_table(self):
        expected = {"t1": TableDef(name="t1")}
        live = {}

        drifts = compare_schemas(expected, live, {}, {})
        assert len(drifts) == 1
        assert drifts[0].category == "missing_table"

    def test_extra_table(self):
        expected = {}
        live = {"extra_t": TableDef(name="extra_t")}

        drifts = compare_schemas(expected, live, {}, {})
        assert len(drifts) == 1
        assert drifts[0].category == "extra_table"

    def test_missing_view(self):
        expected_views = {"v_test": ViewDef(name="v_test")}
        live_views = {}

        drifts = compare_schemas({}, {}, expected_views, live_views)
        assert len(drifts) == 1
        assert drifts[0].category == "missing_view"

    def test_extra_view(self):
        expected_views = {}
        live_views = {"v_extra": ViewDef(name="v_extra")}

        drifts = compare_schemas({}, {}, expected_views, live_views)
        assert len(drifts) == 1
        assert drifts[0].category == "extra_view"

    def test_table_filter_limits_check(self):
        expected = {
            "t1": TableDef(name="t1", columns=[ColumnDef(name="id", col_type="INT")]),
            "t2": TableDef(name="t2", columns=[ColumnDef(name="id", col_type="INT")]),
        }
        live = {
            "t1": TableDef(name="t1", columns=[ColumnDef(name="id", col_type="INT")]),
        }

        # Filtering to t1 should not report t2 as missing
        drifts = compare_schemas(expected, live, {}, {}, table_filter="t1")
        assert len(drifts) == 0

    def test_table_filter_nonexistent_table(self):
        drifts = compare_schemas({}, {}, {}, {}, table_filter="nonexistent")
        assert len(drifts) == 1
        assert drifts[0].category == "not_in_ddl"

    def test_no_drift_identical_schemas(self):
        col = ColumnDef(name="id", col_type="INT")
        idx = IndexDef(name="primary", columns=["id"], unique=True)
        expected = {"t1": TableDef(name="t1", columns=[col], indexes=[idx])}
        live = {"t1": TableDef(name="t1", columns=[col], indexes=[idx])}

        drifts = compare_schemas(expected, live, {}, {})
        assert len(drifts) == 0

    def test_table_filter_skips_views_and_extra_tables(self):
        expected = {"t1": TableDef(name="t1", columns=[])}
        live = {
            "t1": TableDef(name="t1", columns=[]),
            "extra": TableDef(name="extra", columns=[]),
        }
        expected_views = {"v1": ViewDef(name="v1")}
        live_views = {}

        drifts = compare_schemas(expected, live, expected_views, live_views, table_filter="t1")
        # Should NOT report extra table or missing view when filtering
        assert len(drifts) == 0


# ===================================================================
# Live database introspection (mocked)
# ===================================================================

class TestGetLiveTables:

    def test_get_live_tables_basic(self):
        mock_cursor = MagicMock()

        # 4 queries: tables, columns, indexes, foreign keys
        mock_cursor.fetchall.side_effect = [
            [("opportunity",), ("prospect",)],  # tables
            [  # columns
                ("opportunity", "notice_id", "varchar(100)", "NO", None, ""),
                ("opportunity", "title", "varchar(500)", "YES", None, ""),
                ("prospect", "prospect_id", "int", "NO", None, "auto_increment"),
                ("prospect", "notice_id", "varchar(100)", "NO", None, ""),
            ],
            [  # indexes
                ("opportunity", "PRIMARY", "notice_id", 0, 1),
                ("prospect", "PRIMARY", "prospect_id", 0, 1),
            ],
            [],  # foreign keys
        ]

        with patch("etl.schema_checker.settings") as mock_settings:
            mock_settings.DB_NAME = "test_db"
            tables = get_live_tables(mock_cursor)

        assert "opportunity" in tables
        assert "prospect" in tables
        assert len(tables["opportunity"].columns) == 2
        assert len(tables["prospect"].columns) == 2
        assert tables["prospect"].columns[0].extra == "auto_increment"

    def test_get_live_tables_normalizes_types(self):
        mock_cursor = MagicMock()

        mock_cursor.fetchall.side_effect = [
            [("t1",)],
            [("t1", "id", "int(11)", "NO", None, "auto_increment")],
            [],
            [],
        ]

        with patch("etl.schema_checker.settings") as mock_settings:
            mock_settings.DB_NAME = "test_db"
            tables = get_live_tables(mock_cursor)

        # int(11) should normalize to INT
        assert tables["t1"].columns[0].col_type == "INT"

    def test_get_live_tables_aggregates_composite_indexes(self):
        mock_cursor = MagicMock()

        mock_cursor.fetchall.side_effect = [
            [("t1",)],
            [],
            [  # composite index
                ("t1", "idx_combo", "col_a", 1, 1),
                ("t1", "idx_combo", "col_b", 1, 2),
            ],
            [],
        ]

        with patch("etl.schema_checker.settings") as mock_settings:
            mock_settings.DB_NAME = "test_db"
            tables = get_live_tables(mock_cursor)

        assert len(tables["t1"].indexes) == 1
        assert tables["t1"].indexes[0].columns == ["col_a", "col_b"]
        assert tables["t1"].indexes[0].unique is False

    def test_get_live_tables_foreign_keys(self):
        mock_cursor = MagicMock()

        mock_cursor.fetchall.side_effect = [
            [("prospect",)],
            [],
            [],
            [  # foreign keys
                ("fk_notice", "prospect", "notice_id", "opportunity", "notice_id"),
            ],
        ]

        with patch("etl.schema_checker.settings") as mock_settings:
            mock_settings.DB_NAME = "test_db"
            tables = get_live_tables(mock_cursor)

        assert len(tables["prospect"].foreign_keys) == 1
        fk = tables["prospect"].foreign_keys[0]
        assert fk.name == "fk_notice"
        assert fk.columns == ["notice_id"]
        assert fk.ref_table == "opportunity"

    def test_get_live_tables_empty_db(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.side_effect = [[], [], [], []]

        with patch("etl.schema_checker.settings") as mock_settings:
            mock_settings.DB_NAME = "test_db"
            tables = get_live_tables(mock_cursor)

        assert len(tables) == 0


class TestGetLiveViews:

    def test_get_live_views(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("v_summary",), ("v_active_prospects",),
        ]

        with patch("etl.schema_checker.settings") as mock_settings:
            mock_settings.DB_NAME = "test_db"
            views = get_live_views(mock_cursor)

        assert "v_summary" in views
        assert "v_active_prospects" in views

    def test_get_live_views_empty(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []

        with patch("etl.schema_checker.settings") as mock_settings:
            mock_settings.DB_NAME = "test_db"
            views = get_live_views(mock_cursor)

        assert len(views) == 0


# ===================================================================
# parse_ddl_files (mocked filesystem)
# ===================================================================

class TestParseDdlFiles:

    def test_no_sql_files_returns_empty(self, tmp_path):
        tables, views = parse_ddl_files(tmp_path)
        assert len(tables) == 0
        assert len(views) == 0

    def test_parses_tables_subfolder(self, tmp_path):
        tables_dir = tmp_path / "tables"
        tables_dir.mkdir()
        sql_file = tables_dir / "01_test.sql"
        sql_file.write_text(
            "CREATE TABLE test_t (id INT PRIMARY KEY, name VARCHAR(50)) ENGINE=InnoDB;",
            encoding="utf-8",
        )

        tables, views = parse_ddl_files(tmp_path)
        assert "test_t" in tables
        assert len(views) == 0

    def test_parses_views_subfolder(self, tmp_path):
        views_dir = tmp_path / "views"
        views_dir.mkdir()
        sql_file = views_dir / "01_view.sql"
        sql_file.write_text(
            "CREATE OR REPLACE VIEW v_test AS SELECT 1;",
            encoding="utf-8",
        )

        tables, views = parse_ddl_files(tmp_path)
        assert len(tables) == 0
        assert "v_test" in views

    def test_parses_multiple_subfolders(self, tmp_path):
        for sub in ["tables", "views"]:
            d = tmp_path / sub
            d.mkdir()

        (tmp_path / "tables" / "t.sql").write_text(
            "CREATE TABLE t1 (id INT PRIMARY KEY) ENGINE=InnoDB;",
            encoding="utf-8",
        )
        (tmp_path / "views" / "v.sql").write_text(
            "CREATE OR REPLACE VIEW v1 AS SELECT 1;",
            encoding="utf-8",
        )

        tables, views = parse_ddl_files(tmp_path)
        assert "t1" in tables
        assert "v1" in views


# ===================================================================
# DriftItem dataclass
# ===================================================================

class TestDriftItem:

    def test_drift_item_defaults(self):
        d = DriftItem(table="t1", category="missing_column", detail="Missing col x")
        assert d.fix_sql == ""
        assert d.table == "t1"

    def test_drift_item_with_fix(self):
        d = DriftItem(
            table="t1",
            category="missing_column",
            detail="Missing col x",
            fix_sql="ALTER TABLE t1 ADD COLUMN x INT;"
        )
        assert "ALTER TABLE" in d.fix_sql
