"""Backup fed_contracts MySQL database using mysqldump.

Creates a gzip-compressed SQL dump with automatic retention cleanup.

Usage:
    python scripts/backup_db.py
    python scripts/backup_db.py --retain-days 14
    python scripts/backup_db.py --backup-dir /mnt/backups
    python scripts/backup_db.py --help
"""

import argparse
import gzip
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# Allow running from project root or fed_prospector/
SCRIPT_DIR = Path(__file__).resolve().parent
FED_PROSPECTOR_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = FED_PROSPECTOR_DIR.parent

# Load .env from fed_prospector/.env
from dotenv import load_dotenv

load_dotenv(FED_PROSPECTOR_DIR / ".env")

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "fed_contracts")
DB_USER = os.getenv("DB_USER", "fed_app")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")


def get_backup_dir(override: str | None = None) -> Path:
    """Resolve backup directory from argument, env var, or default."""
    if override:
        return Path(override).resolve()
    env_dir = os.getenv("BACKUP_DIR")
    if env_dir:
        return Path(env_dir).resolve()
    return PROJECT_ROOT / "backups"


def run_backup(backup_dir: Path) -> Path:
    """Run mysqldump and compress output. Returns path to backup file."""
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{DB_NAME}_{timestamp}.sql.gz"
    backup_path = backup_dir / filename

    cmd = [
        "mysqldump",
        f"--host={DB_HOST}",
        f"--port={DB_PORT}",
        f"--user={DB_USER}",
        "--single-transaction",
        "--routines",
        "--triggers",
        "--set-gtid-purged=OFF",
        DB_NAME,
    ]

    env = os.environ.copy()
    env["MYSQL_PWD"] = DB_PASSWORD

    print(f"Backing up {DB_NAME} on {DB_HOST}:{DB_PORT}...")
    start = time.time()

    result = subprocess.run(
        cmd, capture_output=True, env=env, timeout=3600
    )

    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace")
        print(f"ERROR: mysqldump failed (exit {result.returncode})", file=sys.stderr)
        print(stderr, file=sys.stderr)
        sys.exit(1)

    # Compress
    with gzip.open(backup_path, "wb") as f:
        f.write(result.stdout)

    elapsed = time.time() - start
    size_mb = backup_path.stat().st_size / (1024 * 1024)
    print(f"Backup complete: {backup_path}")
    print(f"  Size: {size_mb:.1f} MB, Time: {elapsed:.1f}s")
    return backup_path


def cleanup_old_backups(backup_dir: Path, retain_days: int) -> None:
    """Delete backup files older than retain_days."""
    if retain_days <= 0:
        return

    cutoff = datetime.now() - timedelta(days=retain_days)
    removed = 0

    for f in backup_dir.glob(f"{DB_NAME}_*.sql.gz"):
        mtime = datetime.fromtimestamp(f.stat().st_mtime)
        if mtime < cutoff:
            f.unlink()
            print(f"  Deleted old backup: {f.name}")
            removed += 1

    if removed:
        print(f"  Removed {removed} backup(s) older than {retain_days} days")
    else:
        print(f"  No backups older than {retain_days} days to remove")


def main():
    parser = argparse.ArgumentParser(
        description="Backup fed_contracts MySQL database using mysqldump."
    )
    parser.add_argument(
        "--backup-dir",
        help="Directory to store backups (default: BACKUP_DIR env var or backups/)",
    )
    parser.add_argument(
        "--retain-days",
        type=int,
        default=30,
        help="Delete backups older than N days (default: 30, 0 to disable)",
    )
    args = parser.parse_args()

    if not DB_PASSWORD:
        print("ERROR: DB_PASSWORD not set. Check fed_prospector/.env", file=sys.stderr)
        sys.exit(1)

    backup_dir = get_backup_dir(args.backup_dir)
    run_backup(backup_dir)

    print("Cleaning up old backups...")
    cleanup_old_backups(backup_dir, args.retain_days)
    print("Done.")


if __name__ == "__main__":
    main()
