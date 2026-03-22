"""Download attachments from SAM.gov opportunity resource links.

Reads the resource_links JSON column from the opportunity table, downloads
each attachment file, computes a SHA-256 content hash, and stores metadata
in the opportunity_attachment table.

Implements SSRF protection, redirect validation, Content-Type filtering,
and file-size limits.  Integrates with LoadManager for ETL load tracking.
"""

import hashlib
import json
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests

from db.connection import get_connection
from etl.load_manager import LoadManager
from etl.resource_link_resolver import _ALLOWED_PREFIXES, _parse_content_disposition

logger = logging.getLogger("fed_prospector.etl.attachment_downloader")

# Redirect targets must match *.amazonaws.com
_ALLOWED_REDIRECT_PATTERN = re.compile(r"^https://[a-z0-9._-]+\.amazonaws\.com/")

# Default download directory (relative to fed_prospector/)
_DEFAULT_ATTACHMENT_DIR = Path(os.environ.get("ATTACHMENT_DIR", r"E:\fedprospector\attachments"))

# Request timeout (seconds) for the download stream
_REQUEST_TIMEOUT = 60

# Stream chunk size
_CHUNK_SIZE = 8192


class AttachmentDownloader:
    """Download SAM.gov opportunity attachments and track in opportunity_attachment."""

    def __init__(self, db_connection=None, load_manager=None, attachment_dir=None):
        """Initialize the downloader.

        Args:
            db_connection: Not used (connections obtained from pool). Kept for
                           interface compatibility with other loaders.
            load_manager: Optional LoadManager instance.
            attachment_dir: Override base directory for downloaded files.
        """
        self.load_manager = load_manager or LoadManager()
        self.attachment_dir = Path(attachment_dir) if attachment_dir else _DEFAULT_ATTACHMENT_DIR

    # =================================================================
    # Public entry point
    # =================================================================

    def download_attachments(
        self,
        notice_id=None,
        batch_size=100,
        max_file_size_mb=50,
        missing_only=True,
        check_changed=False,
        delay=0.1,
        active_only=False,
        workers=5,
    ):
        """Download attachments for opportunities with resource_links.

        Args:
            notice_id: If provided, only download for this opportunity.
            batch_size: Number of opportunities to process per DB query batch.
            max_file_size_mb: Skip files larger than this (MB).
            missing_only: If True (default), skip URLs already downloaded.
            check_changed: If True, re-download and compare content_hash;
                           skip if unchanged.
            delay: Seconds to wait between downloads (rate limiting).
            active_only: If True, only process opportunities whose
                         response_deadline is in the future (or NULL).
            workers: Number of concurrent download threads (default 5).

        Returns:
            dict with keys: downloaded, skipped, failed, total_urls
        """
        max_file_size_bytes = max_file_size_mb * 1024 * 1024
        stats = {"downloaded": 0, "skipped": 0, "failed": 0, "total_urls": 0}

        # Start ETL load tracking
        load_id = self.load_manager.start_load(
            source_system="ATTACHMENT_DOWNLOAD",
            load_type="INCREMENTAL",
            parameters={
                "notice_id": notice_id,
                "batch_size": batch_size,
                "max_file_size_mb": max_file_size_mb,
                "missing_only": missing_only,
                "check_changed": check_changed,
                "active_only": active_only,
            },
        )

        try:
            urls_to_download = self._query_urls(notice_id, batch_size, missing_only, active_only)
            stats["total_urls"] = len(urls_to_download)
            logger.info("Found %d attachment URLs to process (load_id=%d)",
                        len(urls_to_download), load_id)

            from concurrent.futures import ThreadPoolExecutor, as_completed
            from threading import Lock
            from tqdm import tqdm

            stats_lock = Lock()

            def _download_one(opp_notice_id, url):
                """Download a single file and return the result."""
                if delay > 0:
                    time.sleep(delay)
                try:
                    result = self._download_single(
                        opp_notice_id, url, max_file_size_bytes,
                        check_changed, load_id,
                    )
                    return result
                except Exception:
                    logger.exception("Unexpected error downloading %s for %s",
                                     url, opp_notice_id)
                    self._upsert_attachment_row(
                        opp_notice_id, url, download_status="failed", load_id=load_id,
                    )
                    return "error"

            pbar = tqdm(
                total=len(urls_to_download),
                desc="Downloading",
                unit="file",
                bar_format="{desc}: {n_fmt}/{total_fmt} [{elapsed}<{remaining}] {postfix}",
            )

            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {
                    executor.submit(_download_one, opp_id, url): (opp_id, url)
                    for opp_id, url in urls_to_download
                }
                for future in as_completed(futures):
                    result = future.result()
                    with stats_lock:
                        if result == "downloaded":
                            stats["downloaded"] += 1
                        elif result == "skipped":
                            stats["skipped"] += 1
                        else:
                            stats["failed"] += 1
                        pbar.update(1)
                        pbar.set_postfix_str(
                            f"ok={stats['downloaded']} skip={stats['skipped']} fail={stats['failed']}"
                        )

            pbar.close()

            self.load_manager.complete_load(
                load_id,
                records_read=stats["total_urls"],
                records_inserted=stats["downloaded"],
                records_unchanged=stats["skipped"],
                records_errored=stats["failed"],
            )

        except Exception as exc:
            logger.exception("Attachment download batch failed")
            self.load_manager.fail_load(load_id, str(exc))
            raise

        logger.info(
            "Attachment download complete: %d downloaded, %d skipped, %d failed (of %d total)",
            stats["downloaded"], stats["skipped"], stats["failed"], stats["total_urls"],
        )
        return stats

    # =================================================================
    # Internal methods
    # =================================================================

    def _query_urls(self, notice_id, batch_size, missing_only, active_only=False):
        """Query opportunity table for resource_links URLs to download.

        Args:
            notice_id: If provided, only query this opportunity.
            batch_size: Max opportunities to query.
            missing_only: Filter out already-downloaded URLs.
            active_only: If True, only include opportunities with future
                         response_deadline (or NULL deadline).

        Returns:
            list of (notice_id, url) tuples
        """
        active_filter = (
            " AND (o.response_deadline >= NOW() OR o.response_deadline IS NULL)"
            if active_only else ""
        )

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            if notice_id:
                cursor.execute(
                    "SELECT o.notice_id, o.resource_links FROM opportunity o "
                    "WHERE o.notice_id = %s AND o.resource_links IS NOT NULL"
                    + active_filter,
                    (notice_id,),
                )
            else:
                # When missing_only, exclude opps where ALL URLs are already
                # in opportunity_attachment so LIMIT finds opps with actual
                # work to do instead of re-fetching already-processed ones.
                missing_filter = ""
                if missing_only:
                    missing_filter = (
                        " AND o.notice_id NOT IN ("
                        "  SELECT DISTINCT oa.notice_id FROM opportunity_attachment oa"
                        "  WHERE oa.download_status IN ('downloaded', 'skipped')"
                        "  GROUP BY oa.notice_id"
                        "  HAVING COUNT(*) >= ("
                        "    SELECT JSON_LENGTH(o2.resource_links)"
                        "    FROM opportunity o2 WHERE o2.notice_id = oa.notice_id"
                        "  )"
                        ")"
                    )
                cursor.execute(
                    "SELECT o.notice_id, o.resource_links FROM opportunity o "
                    "WHERE o.resource_links IS NOT NULL"
                    + active_filter
                    + missing_filter
                    + " LIMIT %s",
                    (batch_size,),
                )
            rows = cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

        # Parse JSON resource_links and build (notice_id, url) pairs
        url_pairs = []
        for row in rows:
            links = row["resource_links"]
            if isinstance(links, str):
                try:
                    links = json.loads(links)
                except (json.JSONDecodeError, TypeError):
                    logger.warning("Invalid resource_links JSON for %s", row["notice_id"])
                    continue
            if not isinstance(links, list):
                continue
            for link in links:
                url = link if isinstance(link, str) else link.get("url") if isinstance(link, dict) else None
                if url:
                    url_pairs.append((row["notice_id"], url))

        if not missing_only:
            return url_pairs

        # Filter out URLs already downloaded
        if not url_pairs:
            return url_pairs

        conn = get_connection()
        cursor = conn.cursor()
        try:
            # Build a set of (notice_id, url) already downloaded
            placeholders = ", ".join(["(%s, %s)"] * len(url_pairs))
            flat_params = []
            for nid, u in url_pairs:
                flat_params.extend([nid, u])
            cursor.execute(
                f"SELECT notice_id, url FROM opportunity_attachment "
                f"WHERE download_status = 'downloaded' "
                f"AND (notice_id, url) IN ({placeholders})",
                flat_params,
            )
            already_downloaded = {(r[0], r[1]) for r in cursor.fetchall()}
        finally:
            cursor.close()
            conn.close()

        return [(nid, u) for nid, u in url_pairs if (nid, u) not in already_downloaded]

    def _download_single(self, notice_id, url, max_file_size_bytes, check_changed, load_id):
        """Download a single attachment URL.

        Returns:
            'downloaded', 'skipped', or 'failed'
        """
        # SSRF protection
        if not any(url.startswith(prefix) for prefix in _ALLOWED_PREFIXES):
            logger.warning("Blocked non-SAM.gov URL (SSRF protection): %s", url)
            self._upsert_attachment_row(
                notice_id, url, download_status="skipped", load_id=load_id,
            )
            return "skipped"

        # Make the request, following redirects manually to validate target
        try:
            resp = requests.get(
                url,
                allow_redirects=False,
                timeout=_REQUEST_TIMEOUT,
                stream=True,
            )
        except requests.RequestException as exc:
            logger.warning("Request failed for %s: %s", url, exc)
            self._upsert_attachment_row(
                notice_id, url, download_status="failed", load_id=load_id,
            )
            return "failed"

        # Handle 303 redirect (SAM.gov -> S3)
        if resp.status_code in (301, 302, 303, 307, 308):
            redirect_url = resp.headers.get("Location")
            if not redirect_url:
                logger.warning("Redirect with no Location header for %s", url)
                self._upsert_attachment_row(
                    notice_id, url, download_status="failed", load_id=load_id,
                )
                return "failed"

            # Validate redirect target
            if not _ALLOWED_REDIRECT_PATTERN.match(redirect_url):
                logger.warning("Blocked redirect to non-S3 target: %s -> %s",
                               url, redirect_url)
                self._upsert_attachment_row(
                    notice_id, url, download_status="skipped", load_id=load_id,
                )
                return "skipped"

            # Extract filename from 303 response headers before following redirect
            filename = self._extract_filename(resp, url)

            resp.close()
            try:
                resp = requests.get(
                    redirect_url,
                    timeout=_REQUEST_TIMEOUT,
                    stream=True,
                )
            except requests.RequestException as exc:
                logger.warning("Redirect download failed for %s: %s", url, exc)
                self._upsert_attachment_row(
                    notice_id, url, download_status="failed", load_id=load_id,
                )
                return "failed"
        else:
            filename = self._extract_filename(resp, url)

        if resp.status_code != 200:
            logger.warning("HTTP %d for %s", resp.status_code, url)
            resp.close()
            self._upsert_attachment_row(
                notice_id, url, download_status="failed", load_id=load_id,
            )
            return "failed"

        # Validate Content-Type (reject HTML error pages)
        content_type = resp.headers.get("Content-Type", "")
        content_type_clean = content_type.split(";")[0].strip().lower()
        if content_type_clean == "text/html":
            logger.warning("Rejected text/html content for %s", url)
            resp.close()
            self._upsert_attachment_row(
                notice_id, url, download_status="skipped",
                content_type=content_type_clean, load_id=load_id,
            )
            return "skipped"

        # Check Content-Length if available
        content_length = resp.headers.get("Content-Length")
        if content_length and int(content_length) > max_file_size_bytes:
            logger.info("Skipping oversized file (%s bytes) for %s",
                        content_length, url)
            resp.close()
            self._upsert_attachment_row(
                notice_id, url, download_status="skipped",
                content_type=content_type_clean,
                file_size_bytes=int(content_length), load_id=load_id,
            )
            return "skipped"

        # Ensure filename
        if not filename:
            filename = self._filename_from_url(url)

        # Sanitize filename
        filename = self._sanitize_filename(filename)

        # Stream download to disk
        dest_dir = self.attachment_dir / notice_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / filename

        hasher = hashlib.sha256()
        file_size = 0
        try:
            with open(dest_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=_CHUNK_SIZE):
                    if chunk:
                        file_size += len(chunk)
                        if file_size > max_file_size_bytes:
                            logger.info("File exceeded max size during download: %s", url)
                            f.close()
                            dest_path.unlink(missing_ok=True)
                            self._upsert_attachment_row(
                                notice_id, url, download_status="skipped",
                                content_type=content_type_clean, load_id=load_id,
                            )
                            return "skipped"
                        f.write(chunk)
                        hasher.update(chunk)
        except Exception:
            logger.exception("Error writing file for %s", url)
            dest_path.unlink(missing_ok=True)
            self._upsert_attachment_row(
                notice_id, url, download_status="failed", load_id=load_id,
            )
            return "failed"
        finally:
            resp.close()

        content_hash = hasher.hexdigest()

        # check_changed: compare hash with existing row
        if check_changed:
            existing_hash = self._get_existing_hash(notice_id, url)
            if existing_hash == content_hash:
                logger.debug("Hash unchanged for %s, skipping", url)
                dest_path.unlink(missing_ok=True)
                return "skipped"

        # Store relative path from attachment_dir
        relative_path = f"{notice_id}/{filename}"

        self._upsert_attachment_row(
            notice_id, url,
            filename=filename,
            content_type=content_type_clean,
            file_size_bytes=file_size,
            file_path=relative_path,
            download_status="downloaded",
            content_hash=content_hash,
            downloaded_at=datetime.now(),
            load_id=load_id,
        )

        logger.debug("Downloaded %s (%d bytes, hash=%s)", filename, file_size, content_hash[:12])
        return "downloaded"

    def _extract_filename(self, resp, url):
        """Extract filename from Content-Disposition header or URL."""
        content_disp = resp.headers.get("Content-Disposition")
        if content_disp:
            filename = _parse_content_disposition(content_disp)
            if filename:
                return filename
        return None

    def _filename_from_url(self, url):
        """Derive a filename from the URL path."""
        parsed = urlparse(url)
        path_parts = parsed.path.rstrip("/").split("/")
        # SAM.gov URLs end in .../download, so try second-to-last segment
        for part in reversed(path_parts):
            if part and part != "download":
                decoded = unquote(part)
                if "." in decoded:
                    return decoded
        # Fallback: use a hash of the URL
        return hashlib.md5(url.encode()).hexdigest()[:16] + ".bin"

    @staticmethod
    def _sanitize_filename(filename):
        """Remove or replace characters unsafe for file paths."""
        # Replace path separators and null bytes
        filename = filename.replace("/", "_").replace("\\", "_").replace("\0", "")
        # Truncate to reasonable length
        if len(filename) > 200:
            name, _, ext = filename.rpartition(".")
            if ext and len(ext) <= 10:
                filename = name[:200 - len(ext) - 1] + "." + ext
            else:
                filename = filename[:200]
        return filename

    def _get_existing_hash(self, notice_id, url):
        """Get the content_hash of an existing attachment row, or None."""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT content_hash FROM opportunity_attachment "
                "WHERE notice_id = %s AND url = %s",
                (notice_id, url),
            )
            row = cursor.fetchone()
            return row[0] if row else None
        finally:
            cursor.close()
            conn.close()

    def _upsert_attachment_row(
        self,
        notice_id,
        url,
        filename=None,
        content_type=None,
        file_size_bytes=None,
        file_path=None,
        download_status="pending",
        content_hash=None,
        downloaded_at=None,
        load_id=None,
    ):
        """INSERT or UPDATE an opportunity_attachment row."""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO opportunity_attachment "
                "(notice_id, url, filename, content_type, file_size_bytes, "
                " file_path, download_status, content_hash, downloaded_at, last_load_id) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "ON DUPLICATE KEY UPDATE "
                "filename = COALESCE(VALUES(filename), filename), "
                "content_type = COALESCE(VALUES(content_type), content_type), "
                "file_size_bytes = COALESCE(VALUES(file_size_bytes), file_size_bytes), "
                "file_path = COALESCE(VALUES(file_path), file_path), "
                "download_status = VALUES(download_status), "
                "content_hash = COALESCE(VALUES(content_hash), content_hash), "
                "downloaded_at = COALESCE(VALUES(downloaded_at), downloaded_at), "
                "last_load_id = VALUES(last_load_id)",
                (
                    notice_id, url[:500], filename, content_type, file_size_bytes,
                    file_path, download_status, content_hash, downloaded_at, load_id,
                ),
            )
            conn.commit()
        finally:
            cursor.close()
            conn.close()
