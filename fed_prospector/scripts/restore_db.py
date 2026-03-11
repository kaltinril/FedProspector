"""Restore fed_contracts MySQL database from a backup file.

Supports both .sql.gz (compressed) and .sql (plain) backup files.

Usage:
    python scripts/restore_db.py backups/fed_contracts_20260310_120000.sql.gz
    python scripts/restore_db.py backup.sql --yes
    python scripts/restore_db.py --help
"""

import argparse
import gzip
import os
import subprocess
import sys
import time
from pathlib import Path

# Allow running from project root or fed_prospector/
SCRIPT_DIR = Path(__file__).resolve().parent
FED_PROSPECTOR_DIR = SCRIPT_DIR.parent

# Load .env from fed_prospector/.env
from dotenv import load_dotenv

load_dotenv(FED_PROSPECTOR_DIR / ".env")

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "fed_contracts")
DB_USER = os.getenv("DB_USER", "fed_app")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")


def restore(backup_path: Path) -> None:
    """Restore database from a backup file."""
    cmd = [
        "mysql",
        f"--host={DB_HOST}",
        f"--port={DB_PORT}",
        f"--user={DB_USER}",
        DB_NAME,
    ]

    env = os.environ.copy()
    env["MYSQL_PWD"] = DB_PASSWORD

    # Read input data (decompress if needed)
    if backup_path.suffix == ".gz" or backup_path.name.endswith(".sql.gz"):
        print(f"Decompressing {backup_path.name}...")
        with gzip.open(backup_path, "rb") as f:
            sql_data = f.read()
    else:
        sql_data = backup_path.read_bytes()

    print(f"Restoring {DB_NAME} from {backup_path.name}...")
    start = time.time()

    result = subprocess.run(
        cmd, input=sql_data, capture_output=True, env=env, timeout=3600
    )

    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace")
        print(f"ERROR: mysql restore failed (exit {result.returncode})", file=sys.stderr)
        print(stderr, file=sys.stderr)
        sys.exit(1)

    elapsed = time.time() - start
    print(f"Restore complete in {elapsed:.1f}s")


def main():
    parser = argparse.ArgumentParser(
        description="Restore fed_contracts database from a mysqldump backup file."
    )
    parser.add_argument(
        "backup_file",
        help="Path to backup file (.sql or .sql.gz)",
    )
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip confirmation prompt",
    )
    args = parser.parse_args()

    backup_path = Path(args.backup_file).resolve()

    if not backup_path.exists():
        print(f"ERROR: File not found: {backup_path}", file=sys.stderr)
        sys.exit(1)

    if not DB_PASSWORD:
        print("ERROR: DB_PASSWORD not set. Check fed_prospector/.env", file=sys.stderr)
        sys.exit(1)

    size_mb = backup_path.stat().st_size / (1024 * 1024)

    if not args.yes:
        print(f"This will OVERWRITE the '{DB_NAME}' database on {DB_HOST}:{DB_PORT}")
        print(f"  Backup file: {backup_path}")
        print(f"  File size:   {size_mb:.1f} MB")
        confirm = input("Continue? [y/N] ").strip().lower()
        if confirm != "y":
            print("Aborted.")
            sys.exit(0)

    restore(backup_path)
    print("Done.")


if __name__ == "__main__":
    main()
