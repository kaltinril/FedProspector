"""Manual tests for etl/attachment_cleanup.py (no DB required)."""

import inspect
import os
import re
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock db.connection and etl.load_manager before importing the module
sys.modules["db.connection"] = MagicMock()
sys.modules["etl.load_manager"] = MagicMock()
# LoadManager needs to be callable (it's instantiated in __init__)
sys.modules["etl.load_manager"].LoadManager = MagicMock

results = []


def record(name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    results.append((name, passed))
    print(f"  [{status}] {name}")
    if detail:
        print(f"         {detail}")


# ── Import the module ──
try:
    from etl.attachment_cleanup import AttachmentFileCleanup, _DEFAULT_ATTACHMENT_DIR
    import_ok = True
except Exception as e:
    import_ok = False
    import_err = str(e)

# ═══════════════════════════════════════════════════════════════════
# Test 1: Module imports and class instantiation
# ═══════════════════════════════════════════════════════════════════
print("\n=== Test 1: Module imports and class instantiation ===")

record("Module imports successfully", import_ok,
       "" if import_ok else f"Import error: {import_err}")

if import_ok:
    obj = AttachmentFileCleanup(db_connection=MagicMock())
    record("Class instantiates with no positional args (db mock only)",
           obj is not None)

    expected_suffix = Path("fed_prospector") / "data" / "attachments"
    actual = str(obj.attachment_dir).replace("\\", "/")
    record("Default attachment_dir ends with fed_prospector/data/attachments",
           actual.endswith("fed_prospector/data/attachments"),
           f"actual={actual}")

    record("Default attachment_dir is a Path instance",
           isinstance(obj.attachment_dir, Path))

    record("_DEFAULT_ATTACHMENT_DIR is absolute",
           _DEFAULT_ATTACHMENT_DIR.is_absolute(),
           f"value={_DEFAULT_ATTACHMENT_DIR}")

# ═══════════════════════════════════════════════════════════════════
# Test 2: Custom attachment_dir
# ═══════════════════════════════════════════════════════════════════
print("\n=== Test 2: Custom attachment_dir ===")

if import_ok:
    custom = AttachmentFileCleanup(
        db_connection=MagicMock(),
        attachment_dir="/tmp/my_custom_dir"
    )
    record("Custom attachment_dir stored as Path",
           isinstance(custom.attachment_dir, Path))
    record("Custom attachment_dir value correct",
           str(custom.attachment_dir).replace("\\", "/") == "/tmp/my_custom_dir",
           f"actual={custom.attachment_dir}")

    # Also test with a string that looks like a Windows path
    custom2 = AttachmentFileCleanup(
        db_connection=MagicMock(),
        attachment_dir=r"C:\data\attachments"
    )
    record("Windows-style path stored as Path",
           isinstance(custom2.attachment_dir, Path))

# ═══════════════════════════════════════════════════════════════════
# Test 3: File deletion logic (mock DB, real filesystem)
# ═══════════════════════════════════════════════════════════════════
print("\n=== Test 3: File deletion logic (real filesystem) ===")

if import_ok:
    tmpdir = tempfile.mkdtemp(prefix="attachment_cleanup_test_")
    try:
        # Create directory structure
        notice123 = Path(tmpdir) / "notice123"
        notice456 = Path(tmpdir) / "notice456"
        notice123.mkdir()
        notice456.mkdir()

        doc_pdf = notice123 / "document.pdf"
        other_docx = notice123 / "other.docx"
        report_pdf = notice456 / "report.pdf"

        doc_pdf.write_bytes(b"x" * 100)
        other_docx.write_bytes(b"y" * 80)
        report_pdf.write_bytes(b"z" * 120)

        # Verify files exist
        record("All 3 test files created successfully",
               doc_pdf.is_file() and other_docx.is_file() and report_pdf.is_file())

        # Test 3a: Delete one file, verify it's gone
        doc_pdf.unlink()
        record("unlink() removes single file",
               not doc_pdf.is_file() and other_docx.is_file())

        # Test 3b: rmdir on non-empty directory should fail
        try:
            notice123.rmdir()
            record("rmdir on non-empty dir raises OSError", False,
                   "Should have raised OSError")
        except OSError:
            record("rmdir on non-empty dir raises OSError", True)

        # Test 3c: Delete remaining file, then rmdir should succeed
        other_docx.unlink()
        record("Second file in notice123 deleted",
               not other_docx.is_file())

        notice123.rmdir()
        record("rmdir on empty dir succeeds",
               not notice123.exists())

        # Test 3d: Verify notice456 still intact
        record("notice456/report.pdf still exists",
               report_pdf.is_file())

        # Test 3e: Test the parent != attachment_dir guard
        # The cleanup code checks: parent != self.attachment_dir
        # If we set attachment_dir = tmpdir, then parent of report.pdf is notice456 != tmpdir -> ok
        record("Parent dir guard: notice456 != tmpdir",
               report_pdf.parent != Path(tmpdir))

    finally:
        # Cleanup
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)
        record("Temp directory cleaned up",
               not Path(tmpdir).exists())

# ═══════════════════════════════════════════════════════════════════
# Test 4: Dry run flag propagation
# ═══════════════════════════════════════════════════════════════════
print("\n=== Test 4: Dry run flag propagation ===")

if import_ok:
    # We need to mock _fetch_eligible to return empty list (avoids DB)
    obj = AttachmentFileCleanup(db_connection=MagicMock())
    obj._fetch_eligible = MagicMock(return_value=[])

    stats_dry = obj.cleanup_files(dry_run=True)
    record("dry_run=True: stats['dry_run'] is True",
           stats_dry.get("dry_run") is True)

    stats_live = obj.cleanup_files(dry_run=False)
    record("dry_run=False: stats['dry_run'] is False",
           stats_live.get("dry_run") is False)

    record("Stats has all expected keys",
           set(stats_dry.keys()) == {"eligible", "deleted", "failed", "bytes_reclaimed", "dry_run"},
           f"keys={set(stats_dry.keys())}")

# ═══════════════════════════════════════════════════════════════════
# Test 5: SQL query validation
# ═══════════════════════════════════════════════════════════════════
print("\n=== Test 5: SQL query validation ===")

if import_ok:
    source = inspect.getsource(AttachmentFileCleanup._fetch_eligible)
    print(f"\n  --- _fetch_eligible source (SQL portion) ---")
    # Extract just the SQL string
    sql_match = re.search(r'sql\s*=\s*"""(.*?)"""', source, re.DOTALL)
    if sql_match:
        sql_text = sql_match.group(1)
        for line in sql_text.strip().splitlines():
            print(f"    {line.strip()}")
    print()

    # Count EXISTS subqueries
    exists_count = len(re.findall(r'\bEXISTS\s*\(', source))
    record("Has exactly TWO EXISTS subqueries",
           exists_count == 2,
           f"found {exists_count} EXISTS clauses")

    # Check first EXISTS for keyword/heuristic
    record("First EXISTS checks extraction_method IN ('keyword', 'heuristic')",
           "extraction_method IN ('keyword', 'heuristic')" in source)

    # Check second EXISTS for AI methods
    record("Second EXISTS checks extraction_method IN ('ai_haiku', 'ai_sonnet')",
           "extraction_method IN ('ai_haiku', 'ai_sonnet')" in source)

    # Both reference oai.attachment_id = oa.attachment_id
    join_refs = re.findall(r'oai\.attachment_id\s*=\s*oa\.attachment_id', source)
    record("Both EXISTS use oai.attachment_id = oa.attachment_id",
           len(join_refs) == 2,
           f"found {len(join_refs)} join references")

    # Main WHERE conditions
    record("WHERE has download_status = 'downloaded'",
           "download_status = 'downloaded'" in source)

    record("WHERE has extraction_status = 'extracted'",
           "extraction_status = 'extracted'" in source)

    record("WHERE has file_path IS NOT NULL",
           "file_path IS NOT NULL" in source)

    # notice_id conditional
    record("notice_id adds AND oa.notice_id = %s",
           "oa.notice_id = %s" in source)

    # LIMIT uses batch_size param
    record("LIMIT uses %s parameter (batch_size)",
           "LIMIT %s" in source)

    # Verify params list logic
    record("notice_id param appended conditionally",
           "params.append(notice_id)" in source)

    record("batch_size param appended to params",
           "params.append(batch_size)" in source)

# ═══════════════════════════════════════════════════════════════════
# Test 6: _clear_file_path only clears file_path
# ═══════════════════════════════════════════════════════════════════
print("\n=== Test 6: _clear_file_path only sets file_path = NULL ===")

if import_ok:
    source_clear = inspect.getsource(AttachmentFileCleanup._clear_file_path)
    print(f"\n  --- _clear_file_path source ---")
    for line in source_clear.strip().splitlines():
        print(f"    {line}")
    print()

    # Extract the UPDATE statement
    update_match = re.search(r'"(UPDATE.*?)"', source_clear, re.DOTALL)
    if update_match:
        update_sql = update_match.group(1)
        record("UPDATE statement found",
               True, f"SQL: {update_sql}")

        # Only sets file_path = NULL
        record("SET clause ONLY contains file_path = NULL",
               "SET file_path = NULL" in update_sql,
               f"SET clause in SQL: {update_sql}")

        # Verify no other columns are touched
        dangerous_columns = [
            "extracted_text", "text_hash", "content_hash",
            "download_status", "extraction_status",
            "file_size", "file_name"
        ]
        other_sets = [col for col in dangerous_columns if col in update_sql]
        record("No other columns modified in UPDATE",
               len(other_sets) == 0,
               f"other columns found: {other_sets}" if other_sets else "clean - only file_path touched")

        # Count SET clauses (should be exactly one)
        set_count = update_sql.count("=")
        # attachment_id = %s in WHERE, file_path = NULL in SET -> exactly 2
        record("Exactly 2 '=' in statement (SET + WHERE)",
               set_count == 2,
               f"found {set_count} '=' signs (file_path = NULL + attachment_id = %s)")
    else:
        record("UPDATE statement found", False, "Could not find UPDATE SQL")

# ═══════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
passed = sum(1 for _, p in results if p)
failed = sum(1 for _, p in results if not p)
total = len(results)
print(f"RESULTS: {passed}/{total} passed, {failed} failed")

if failed:
    print("\nFailed tests:")
    for name, p in results:
        if not p:
            print(f"  - {name}")
    sys.exit(1)
else:
    print("\nAll tests passed.")
    sys.exit(0)
