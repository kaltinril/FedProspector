"""Download attachments from SAM.gov opportunity resource links.

Reads the resource_links JSON column from the opportunity table, downloads
each attachment file, computes a SHA-256 content hash, and stores metadata
in the normalized attachment tables (sam_attachment, attachment_document,
opportunity_attachment map).

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

from config.settings import ATTACHMENT_DIR as _DEFAULT_ATTACHMENT_DIR
from db.connection import get_connection
from etl.etl_utils import extract_resource_guid
from etl.load_manager import LoadManager
from etl.resource_link_resolver import _ALLOWED_PREFIXES, _parse_content_disposition

logger = logging.getLogger("fed_prospector.etl.attachment_downloader")

# Redirect targets must match *.amazonaws.com
_ALLOWED_REDIRECT_PATTERN = re.compile(r"^https://[a-z0-9._-]+\.amazonaws\.com/")

# Request timeout (seconds) for the download stream
_REQUEST_TIMEOUT = 60

# Stream chunk size
_CHUNK_SIZE = 8192

# HTTP status codes that indicate the file is permanently gone — no point retrying
_PERMANENT_HTTP_CODES = {400, 403, 404, 410}

# Max retries for transient failures (5xx, timeouts) before auto-skipping
_MAX_DOWNLOAD_RETRIES = 3


class AttachmentDownloader:
    """Download SAM.gov opportunity attachments and track in normalized tables."""

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

            # Deduplicate by resource_guid so concurrent threads don't write
            # to the same filesystem path.  For each unique URL, download once
            # (using the first notice_id) then insert mapping rows for the rest.
            unique_downloads, extra_mappings = self._dedup_by_guid(urls_to_download)
            if len(unique_downloads) < len(urls_to_download):
                logger.info(
                    "Deduplicated %d URLs down to %d unique resource_guids "
                    "(%d extra mapping rows will be created after download)",
                    len(urls_to_download), len(unique_downloads),
                    sum(len(v) for v in extra_mappings.values()),
                )

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
                    # On success, insert mapping rows for other notice_ids
                    # that share the same resource_guid
                    if result in ("downloaded", "skipped"):
                        guid = extract_resource_guid(url)
                        if guid and guid in extra_mappings:
                            existing = self._check_existing_guid(guid)
                            if existing:
                                for extra_nid in extra_mappings[guid]:
                                    self._insert_mapping_row(
                                        extra_nid, url,
                                        existing["attachment_id"], load_id,
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
                    for opp_id, url in unique_downloads
                }
                for future in as_completed(futures):
                    result = future.result()
                    opp_id, url = futures[future]
                    guid = extract_resource_guid(url)
                    # Count the primary download + any extra mappings as processed
                    extra_count = len(extra_mappings.get(guid, [])) if guid else 0
                    with stats_lock:
                        if result == "downloaded":
                            stats["downloaded"] += 1 + extra_count
                        elif result == "skipped":
                            stats["skipped"] += 1 + extra_count
                        else:
                            stats["failed"] += 1 + extra_count
                        pbar.update(1 + extra_count)
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
    # Single-attachment re-download
    # =================================================================

    def redownload_single(self, attachment_id):
        """Re-download a single attachment by its sam_attachment.attachment_id.

        Looks up the URL and resource_guid, re-downloads the file, and
        updates the sam_attachment row.

        Returns:
            dict with keys: processed, downloaded, failed
        """
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT attachment_id, resource_guid, url, file_path "
                "FROM sam_attachment WHERE attachment_id = %s",
                (attachment_id,),
            )
            row = cursor.fetchone()
        finally:
            cursor.close()
            conn.close()

        if not row:
            raise ValueError(f"No sam_attachment found for attachment_id {attachment_id}")

        url = row["url"]
        if not url:
            raise ValueError(f"No URL stored for attachment_id {attachment_id}")

        # Use the existing _download_single method with a dummy load_id
        load_id = self.load_manager.start_load(
            source_system="ATTACHMENT_DOWNLOAD",
            load_type="INCREMENTAL",
            parameters={"attachment_id": attachment_id, "redownload": True},
        )

        # Find the notice_id for this attachment (needed by _download_single)
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT notice_id FROM opportunity_attachment "
                "WHERE attachment_id = %s LIMIT 1",
                (attachment_id,),
            )
            mapping = cursor.fetchone()
        finally:
            cursor.close()
            conn.close()

        notice_id = mapping[0] if mapping else "unknown"

        try:
            result = self._download_single(
                notice_id, url,
                max_file_size_bytes=50 * 1024 * 1024,
                check_changed=False,
                load_id=load_id,
            )

            stats = {"processed": 1, "downloaded": 0, "failed": 0}
            if result == "downloaded":
                stats["downloaded"] = 1
            else:
                stats["failed"] = 1

            self.load_manager.complete_load(
                load_id,
                records_read=1,
                records_inserted=stats["downloaded"],
                records_errored=stats["failed"],
            )
            return stats

        except Exception as exc:
            self.load_manager.fail_load(load_id, str(exc))
            raise

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
                        "  SELECT DISTINCT m.notice_id"
                        "  FROM opportunity_attachment m"
                        "  JOIN sam_attachment sa ON sa.attachment_id = m.attachment_id"
                        "  WHERE sa.download_status IN ('downloaded', 'skipped')"
                        "  GROUP BY m.notice_id"
                        "  HAVING COUNT(*) >= ("
                        "    SELECT JSON_LENGTH(o2.resource_links)"
                        "    FROM opportunity o2 WHERE o2.notice_id = m.notice_id"
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
                f"SELECT m.notice_id, m.url FROM opportunity_attachment m "
                f"JOIN sam_attachment sa ON sa.attachment_id = m.attachment_id "
                f"WHERE sa.download_status IN ('downloaded', 'skipped') "
                f"AND (m.notice_id, m.url) IN ({placeholders})",
                flat_params,
            )
            already_downloaded = {(r[0], r[1]) for r in cursor.fetchall()}
        finally:
            cursor.close()
            conn.close()

        return [(nid, u) for nid, u in url_pairs if (nid, u) not in already_downloaded]

    @staticmethod
    def _dedup_by_guid(url_pairs):
        """Deduplicate (notice_id, url) pairs by resource_guid.

        When multiple notice_ids share the same URL (same resource_guid),
        only one should be downloaded. The rest get mapping rows after
        the download succeeds.

        Returns:
            tuple: (unique_downloads, extra_mappings)
                unique_downloads: list of (notice_id, url) to actually download
                extra_mappings: dict of {resource_guid: [extra_notice_ids]}
        """
        from collections import defaultdict

        guid_groups = defaultdict(list)
        no_guid = []

        for nid, url in url_pairs:
            guid = extract_resource_guid(url)
            if guid:
                guid_groups[guid].append((nid, url))
            else:
                no_guid.append((nid, url))

        unique_downloads = list(no_guid)
        extra_mappings = {}

        for guid, pairs in guid_groups.items():
            # First pair gets downloaded; rest are extra mappings
            unique_downloads.append(pairs[0])
            if len(pairs) > 1:
                extra_mappings[guid] = [nid for nid, _url in pairs[1:]]

        return unique_downloads, extra_mappings

    def _download_single(self, notice_id, url, max_file_size_bytes, check_changed, load_id):
        """Download a single attachment URL.

        Returns:
            'downloaded', 'skipped', or 'failed'
        """
        resource_guid = extract_resource_guid(url)

        # Check if resource_guid already has a downloaded file in sam_attachment.
        # If so, skip download entirely — just insert the mapping row.
        if resource_guid:
            existing = self._check_existing_guid(resource_guid)
            if existing and existing["download_status"] == "downloaded":
                # Already downloaded — just add the mapping row
                self._insert_mapping_row(notice_id, url, existing["attachment_id"], load_id)
                logger.debug(
                    "GUID %s already downloaded — added mapping for %s", resource_guid, notice_id
                )
                return "skipped"

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
            self._mark_transient_failure(notice_id, url, load_id, "network_error")
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
                self._mark_transient_failure(notice_id, url, load_id, "network_error")
                return "failed"
        else:
            filename = self._extract_filename(resp, url)

        if resp.status_code != 200:
            resp.close()
            if resp.status_code in _PERMANENT_HTTP_CODES:
                reason = f"http_{resp.status_code}"
                logger.warning("Permanent HTTP %d for %s — marking skipped (%s)",
                               resp.status_code, url, reason)
                self._upsert_attachment_row(
                    notice_id, url, download_status="skipped",
                    skip_reason=reason, load_id=load_id,
                )
                return "skipped"
            else:
                logger.warning("HTTP %d for %s", resp.status_code, url)
                self._mark_transient_failure(notice_id, url, load_id,
                                             f"http_{resp.status_code}")
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

        # Stream download to disk — use resource_guid-based path if available
        dir_name = resource_guid if resource_guid else notice_id
        dest_dir = self.attachment_dir / dir_name
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
            self._mark_transient_failure(notice_id, url, load_id, "write_error")
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
        relative_path = f"{dir_name}/{filename}"

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
        resource_guid = extract_resource_guid(url)
        conn = get_connection()
        cursor = conn.cursor()
        try:
            if resource_guid:
                cursor.execute(
                    "SELECT content_hash FROM sam_attachment "
                    "WHERE resource_guid = %s",
                    (resource_guid,),
                )
            else:
                cursor.execute(
                    "SELECT content_hash FROM sam_attachment "
                    "WHERE url = %s",
                    (url[:500],),
                )
            row = cursor.fetchone()
            return row[0] if row else None
        finally:
            cursor.close()
            conn.close()

    def _check_existing_guid(self, resource_guid):
        """Check if a resource_guid already exists in sam_attachment.

        Returns dict with attachment_id and download_status, or None.
        """
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT attachment_id, download_status FROM sam_attachment "
                "WHERE resource_guid = %s",
                (resource_guid,),
            )
            return cursor.fetchone()
        finally:
            cursor.close()
            conn.close()

    def _insert_mapping_row(self, notice_id, url, attachment_id, load_id):
        """Insert an opportunity_attachment mapping row (INSERT IGNORE for idempotency)."""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT IGNORE INTO opportunity_attachment "
                "(notice_id, attachment_id, url, last_load_id) "
                "VALUES (%s, %s, %s, %s)",
                (notice_id, attachment_id, url[:500], load_id),
            )
            conn.commit()
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
        skip_reason=None,
    ):
        """Multi-table upsert: sam_attachment + attachment_document + opportunity_attachment map."""
        resource_guid = extract_resource_guid(url)
        if not resource_guid:
            # Non-standard URL — use md5 of URL as fallback GUID
            resource_guid = hashlib.md5(url.encode()).hexdigest()

        conn = get_connection()
        cursor = conn.cursor()
        try:
            # 1. Upsert sam_attachment by resource_guid
            cursor.execute(
                "INSERT INTO sam_attachment "
                "(resource_guid, url, filename, file_size_bytes, "
                " file_path, download_status, content_hash, downloaded_at, last_load_id, skip_reason) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "ON DUPLICATE KEY UPDATE "
                "filename = COALESCE(VALUES(filename), filename), "
                "file_size_bytes = COALESCE(VALUES(file_size_bytes), file_size_bytes), "
                "file_path = COALESCE(VALUES(file_path), file_path), "
                "download_status = VALUES(download_status), "
                "content_hash = COALESCE(VALUES(content_hash), content_hash), "
                "downloaded_at = COALESCE(VALUES(downloaded_at), downloaded_at), "
                "last_load_id = VALUES(last_load_id), "
                "download_retry_count = CASE WHEN VALUES(download_status) = 'downloaded' THEN 0 ELSE download_retry_count END, "
                "skip_reason = VALUES(skip_reason)",
                (
                    resource_guid, url[:500], filename, file_size_bytes,
                    file_path, download_status, content_hash, downloaded_at, load_id,
                    skip_reason,
                ),
            )

            # 2. Get the attachment_id (LAST_INSERT_ID or SELECT)
            attachment_id = cursor.lastrowid
            if not attachment_id:
                cursor.execute(
                    "SELECT attachment_id FROM sam_attachment WHERE resource_guid = %s",
                    (resource_guid,),
                )
                row = cursor.fetchone()
                attachment_id = row[0] if row else None

            # 3. Create attachment_document row if this is a new sam_attachment
            #    (INSERT IGNORE — only creates if attachment_id doesn't exist yet)
            if attachment_id:
                cursor.execute(
                    "INSERT IGNORE INTO attachment_document "
                    "(attachment_id, filename, content_type, last_load_id) "
                    "VALUES (%s, %s, %s, %s)",
                    (attachment_id, filename, content_type, load_id),
                )

            # 4. Insert opportunity_attachment mapping row (INSERT IGNORE for idempotency)
            if attachment_id:
                cursor.execute(
                    "INSERT IGNORE INTO opportunity_attachment "
                    "(notice_id, attachment_id, url, last_load_id) "
                    "VALUES (%s, %s, %s, %s)",
                    (notice_id, attachment_id, url[:500], load_id),
                )

            conn.commit()
        finally:
            cursor.close()
            conn.close()

    def _mark_transient_failure(self, notice_id, url, load_id, reason):
        """Increment retry count; auto-skip if max retries exceeded.

        Operates on sam_attachment by resource_guid. Also ensures the
        opportunity_attachment mapping row exists.
        """
        resource_guid = extract_resource_guid(url)
        if not resource_guid:
            resource_guid = hashlib.md5(url.encode()).hexdigest()

        conn = get_connection()
        cursor = conn.cursor()
        try:
            # Ensure sam_attachment row exists
            cursor.execute(
                "INSERT INTO sam_attachment (resource_guid, url, download_status, last_load_id) "
                "VALUES (%s, %s, 'failed', %s) "
                "ON DUPLICATE KEY UPDATE "
                "download_retry_count = download_retry_count + 1, "
                "download_status = 'failed', "
                "last_load_id = VALUES(last_load_id)",
                (resource_guid, url[:500], load_id),
            )

            # Get attachment_id for mapping row
            cursor.execute(
                "SELECT attachment_id, download_retry_count FROM sam_attachment "
                "WHERE resource_guid = %s",
                (resource_guid,),
            )
            row = cursor.fetchone()
            if row:
                attachment_id, retry_count = row[0], row[1]

                # Ensure attachment_document row exists
                cursor.execute(
                    "INSERT IGNORE INTO attachment_document "
                    "(attachment_id, last_load_id) VALUES (%s, %s)",
                    (attachment_id, load_id),
                )

                # Ensure mapping row exists
                cursor.execute(
                    "INSERT IGNORE INTO opportunity_attachment "
                    "(notice_id, attachment_id, url, last_load_id) "
                    "VALUES (%s, %s, %s, %s)",
                    (notice_id, attachment_id, url[:500], load_id),
                )

                if retry_count >= _MAX_DOWNLOAD_RETRIES:
                    logger.warning(
                        "Max retries (%d) reached for %s — marking skipped (reason: %s)",
                        _MAX_DOWNLOAD_RETRIES, url, reason,
                    )
                    cursor.execute(
                        "UPDATE sam_attachment SET download_status = 'skipped', "
                        "skip_reason = %s WHERE resource_guid = %s",
                        (f"max_retries_{reason}", resource_guid),
                    )
            conn.commit()
        finally:
            cursor.close()
            conn.close()
