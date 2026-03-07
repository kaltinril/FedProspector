"""Resolve SAM.gov resource link URLs to extract filename and content-type metadata.

Makes HEAD requests to SAM.gov resource link URLs. SAM.gov returns a 303 See Other
with Content-Disposition (filename) and Content-Type headers on the 303 response
itself -- we do NOT follow the redirect to S3.

Typical URL: https://sam.gov/api/prod/opps/v3/opportunities/resources/files/{32-hex}/download
All URLs are exactly 104 characters. ~30ms per request, no rate limit, no API key.
"""

import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import unquote

import requests

logger = logging.getLogger("fed_prospector.etl.resource_link_resolver")

# SSRF protection: only allow these URL prefixes
_ALLOWED_PREFIXES = ("https://sam.gov/", "https://api.sam.gov/")

# Timeout for HEAD requests (seconds)
_REQUEST_TIMEOUT = 10

# Delay between each HEAD request (seconds) to avoid overwhelming SAM.gov
_REQUEST_DELAY = 0.1


def resolve_resource_links(urls: list[str], max_concurrent: int = 5) -> list[dict]:
    """HEAD-request each URL, extract filename/content-type from 303 response.

    Args:
        urls: List of SAM.gov resource link URLs.
        max_concurrent: Max parallel HEAD requests.

    Returns:
        List of dicts: {"url": "...", "filename": "...", "content_type": "..."}
        Failed URLs get filename=None, content_type=None.
    """
    results = {}

    with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
        future_to_url = {
            executor.submit(_resolve_single, url): url
            for url in urls
        }
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                results[url] = future.result()
            except Exception as exc:
                logger.warning("Unexpected error resolving %s: %s", url, exc)
                results[url] = {"url": url, "filename": None, "content_type": None}

    # Return in the same order as input
    return [results[url] for url in urls]


def _resolve_single(url: str) -> dict:
    """Resolve a single resource link URL.

    Returns:
        dict with url, filename, content_type.
    """
    result = {"url": url, "filename": None, "content_type": None}

    # SSRF protection
    if not any(url.startswith(prefix) for prefix in _ALLOWED_PREFIXES):
        logger.warning("Skipping non-SAM.gov URL (SSRF protection): %s", url)
        return result

    try:
        time.sleep(_REQUEST_DELAY)  # Be polite to SAM.gov
        resp = requests.head(url, allow_redirects=False, timeout=_REQUEST_TIMEOUT)

        # Extract Content-Type
        content_type = resp.headers.get("Content-Type")
        if content_type:
            # Strip charset or other params: "application/pdf; charset=utf-8" -> "application/pdf"
            result["content_type"] = content_type.split(";")[0].strip()

        # Extract filename from Content-Disposition
        content_disp = resp.headers.get("Content-Disposition")
        if content_disp:
            filename = _parse_content_disposition(content_disp)
            if filename:
                result["filename"] = filename

        # Fallback: URL-decode last path segment if no Content-Disposition filename
        if not result["filename"]:
            # e.g. .../files/abc123/download -> not useful, but guard anyway
            pass

    except requests.RequestException as exc:
        logger.warning("HEAD request failed for %s: %s", url, exc)

    return result


def _parse_content_disposition(header: str) -> str | None:
    """Parse filename from Content-Disposition header.

    Handles:
        attachment; filename="SOW Document.pdf"
        attachment; filename=SOW_Document.pdf
        attachment; filename*=UTF-8''encoded%20name.pdf
    """
    # Try quoted filename first: filename="..."
    match = re.search(r'filename="([^"]+)"', header)
    if match:
        return match.group(1).strip()

    # Try unquoted filename: filename=value
    match = re.search(r"filename=([^\s;]+)", header)
    if match:
        return match.group(1).strip()

    # Try filename* (RFC 5987 encoded)
    match = re.search(r"filename\*=(?:UTF-8|utf-8)''(.+?)(?:;|$)", header)
    if match:
        return unquote(match.group(1).strip())

    return None
