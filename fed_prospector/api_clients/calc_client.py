"""GSA CALC+ Quick Rate API v3 client.

Wraps the CALC+ ceiling rates API for looking up GSA Schedule labor rates.
Provides pricing intelligence for federal proposals by searching ~258,000
contractor labor rates across all GSA schedules.

API docs: https://open.gsa.gov/api/calc/
Endpoint: /ceilingrates/
Auth: NONE required
Rate limits: NONE documented

The v3 API is backed by Elasticsearch. It supports keyword search (labor
category text matching) and sort-based pagination.  Elasticsearch imposes a
max_result_window of 10,000 so a single sorted query can only reach 10K
records.  To retrieve the full ~258K dataset the client combines multiple
sort orderings (each producing a different 10K-record slice) and
de-duplicates by the ES ``_id`` field.
"""

import logging
import tempfile
from pathlib import Path

from api_clients.base_client import BaseAPIClient
from config import settings


logger = logging.getLogger("fed_prospector.api.calc")

RATES_ENDPOINT = "/ceilingrates/"

# Sort orderings used to slice the full dataset into overlapping 10K chunks.
# Each (ordering, direction) pair yields a different 10K-record window from
# Elasticsearch.  De-duplication by _id collapses the overlaps.
_SORT_STRATEGIES = [
    ("vendor_name", "asc"),
    ("vendor_name", "desc"),
    ("labor_category", "asc"),
    ("labor_category", "desc"),
    ("id", "asc"),
    ("id", "desc"),
    ("schedule", "asc"),
    ("schedule", "desc"),
    ("education_level", "asc"),
    ("education_level", "desc"),
    ("worksite", "asc"),
    ("worksite", "desc"),
    ("security_clearance", "asc"),
    ("security_clearance", "desc"),
    ("min_years_experience", "asc"),
    ("min_years_experience", "desc"),
    # Default sort by current_price (both directions)
    (None, "asc"),
    (None, "desc"),
]

# Max results per Elasticsearch query (ES default max_result_window)
_ES_MAX_WINDOW = 10000


class CalcPlusClient(BaseAPIClient):
    """GSA CALC+ Quick Rate API v3 client. No auth, no rate limits.

    The v3 API returns Elasticsearch responses::

        {
          "hits": {
            "total": {"value": 10000, "relation": "gte"},
            "hits": [ {"_id": "...", "_source": { ... rate fields ... }} ]
          },
          "aggregations": { ... }
        }

    Usage:
        client = CalcPlusClient()

        # Search for specific labor categories
        for rate in client.search_rates_all(keyword="software developer"):
            print(rate["labor_category"], rate["current_price"])

        # Get rate summary statistics
        summary = client.get_rate_summary("project manager")
        print(f"Min: ${summary['min']}, Avg: ${summary['avg']}, Max: ${summary['max']}")

        # Iterate through all ~258K rates (multi-query with de-duplication)
        for rate in client.get_all_rates():
            process(rate)
    """

    def __init__(self, db_connection=None):
        """Initialize CALC+ client. No API key needed.

        Args:
            db_connection: Not used (connections obtained from pool). Kept for
                           interface compatibility with other clients.
        """
        super().__init__(
            base_url=settings.CALC_API_BASE_URL,
            api_key="",  # No auth needed
            source_name="GSA_CALC",
            max_daily_requests=999999,  # Effectively unlimited
        )

    # Note: get() is inherited from BaseAPIClient, which skips api_key
    # injection when self.api_key is falsy (empty string). No override
    # needed for CALC+ since api_key="" is passed in __init__.

    # =================================================================
    # ES response helpers
    # =================================================================

    @staticmethod
    def _extract_hits(data):
        """Extract rate dicts from an ES response.

        Pulls records from ``hits.hits[]._source`` and attaches ``_id``
        from the enclosing hit object so the caller can de-duplicate.

        Returns:
            list[dict]: Rate dicts with an added ``_es_id`` key.
        """
        results = []
        for hit in data.get("hits", {}).get("hits", []):
            record = dict(hit.get("_source", {}))
            record["_es_id"] = hit.get("_id")
            results.append(record)
        return results

    @staticmethod
    def _get_total_count(data):
        """Return the total document count from aggregations (most accurate).

        Falls back to hits.total.value which caps at 10,000.
        """
        wage_stats = data.get("aggregations", {}).get("wage_stats", {})
        if wage_stats.get("count"):
            return int(wage_stats["count"])
        total_obj = data.get("hits", {}).get("total", {})
        if isinstance(total_obj, dict):
            return total_obj.get("value", 0)
        return int(total_obj) if total_obj else 0

    # =================================================================
    # Search methods
    # =================================================================

    def search_rates(self, keyword=None, page=1, page_size=100,
                     sort="asc", ordering=None):
        """Search labor ceiling rates.

        Args:
            keyword: Search term for labor category (e.g. "software developer").
            page: Page number (1-based). page * page_size must be <= 10,000.
            page_size: Results per page (default 100, max 10000).
            sort: Sort direction, 'asc' or 'desc'.
            ordering: Sort field (e.g. 'vendor_name', 'id', 'labor_category').
                      None uses default price sort.

        Returns:
            dict: Parsed ES JSON response.
        """
        params = {"page": page, "page_size": page_size, "sort": sort}

        if keyword is not None:
            params["keyword"] = keyword
        if ordering is not None:
            params["ordering"] = ordering

        response = self.get(RATES_ENDPOINT, params=params, timeout=120)
        data = response.json()
        self._validate_response(
            data, ["hits"],
            context="search_rates",
        )
        return data

    def search_rates_all(self, keyword=None, sort="asc", ordering=None):
        """Generator that paginates through matching rates.

        Paginates up to the ES max_result_window (10,000 records).

        Args:
            keyword: Labor category search term.
            sort: Sort direction.
            ordering: Sort field.

        Yields:
            dict: Individual rate records (``_source`` dicts with ``_es_id``).
        """
        page_size = 1000
        page = 1
        total_yielded = 0

        while True:
            # Stop before exceeding ES window
            if page * page_size > _ES_MAX_WINDOW:
                break

            data = self.search_rates(
                keyword=keyword, page=page, page_size=page_size,
                sort=sort, ordering=ordering,
            )
            results = self._extract_hits(data)
            if not results:
                break

            for rate in results:
                total_yielded += 1
                yield rate

            # If we got fewer than page_size, we've exhausted results
            if len(results) < page_size:
                break

            page += 1

        self.logger.info(
            "search_rates_all complete: %d rates in %d page(s) (keyword=%r)",
            total_yielded, page, keyword,
        )

    def get_all_rates(self, progress_callback=None):
        """Retrieve the full dataset using multi-ordering de-duplication.

        The ES backend limits each query to 10,000 results.  To retrieve
        all ~258K records we run multiple queries with different sort
        orderings (each returns a different 10K slice) and de-duplicate
        by ``_es_id``.

        Args:
            progress_callback: Optional callable(seen_count, query_label)
                for progress reporting.

        Yields:
            dict: Individual rate records (de-duplicated).
        """
        seen_ids = set()
        total_yielded = 0
        query_num = 0
        skipped_chunks = 0

        # Fallback sort fields to try when the primary ordering fails.
        _FALLBACK_ORDERINGS = ["id", "price"]

        for ordering, sort_dir in _SORT_STRATEGIES:
            query_num += 1
            label = "%s %s" % (ordering or "default_price", sort_dir)

            data = None
            # Try the primary ordering first, then fallbacks
            attempts = [ordering] + [
                fb for fb in _FALLBACK_ORDERINGS if fb != ordering
            ]
            for attempt_ordering in attempts:
                attempt_label = "%s %s" % (
                    attempt_ordering or "default_price", sort_dir,
                )
                try:
                    data = self.search_rates(
                        page=1, page_size=_ES_MAX_WINDOW,
                        sort=sort_dir, ordering=attempt_ordering,
                    )
                    if attempt_ordering != ordering:
                        self.logger.info(
                            "Fallback sort %r succeeded for chunk %d "
                            "(original: %s)",
                            attempt_label, query_num, label,
                        )
                    break
                except Exception as exc:
                    self.logger.error(
                        "Sort strategy %s failed (chunk %d, offset ~%d): "
                        "%s",
                        attempt_label, query_num,
                        query_num * _ES_MAX_WINDOW, exc,
                    )

            if data is None:
                skipped_chunks += 1
                self.logger.error(
                    "All sort attempts exhausted for chunk %d [%s] "
                    "(offset ~%d) -- skipping",
                    query_num, label, query_num * _ES_MAX_WINDOW,
                )
                continue

            results = self._extract_hits(data)
            new_count = 0

            for rate in results:
                es_id = rate.get("_es_id")
                if es_id and es_id in seen_ids:
                    continue
                if es_id:
                    seen_ids.add(es_id)
                new_count += 1
                total_yielded += 1
                yield rate

            self.logger.info(
                "Strategy %d/%d [%s]: %d hits, %d new (total unique: %d)",
                query_num, len(_SORT_STRATEGIES), label,
                len(results), new_count, len(seen_ids),
            )

            if progress_callback:
                progress_callback(len(seen_ids), label)

        if skipped_chunks:
            self.logger.error(
                "get_all_rates: %d of %d chunks skipped due to errors",
                skipped_chunks, query_num,
            )

        self.logger.info(
            "get_all_rates complete: %d unique rates from %d queries "
            "(%d skipped)",
            total_yielded, query_num, skipped_chunks,
        )

    def download_full_csv(self, progress_callback=None) -> Path:
        """Download the full CALC+ dataset as a CSV bulk export.

        Uses the ``?format=csv&export=y`` query parameters to request
        a streaming CSV download from the CALC+ API.

        Args:
            progress_callback: Optional callable(bytes_written, status_label)
                for progress reporting.

        Returns:
            Path: Path to the downloaded temporary CSV file.  The caller
            is responsible for deleting the file when done.
        """
        url = f"{self.base_url}{RATES_ENDPOINT}"
        params = {"format": "csv", "export": "y"}

        self.logger.info("Downloading full CALC+ CSV export from %s", url)

        response = self.session.get(
            url, params=params, stream=True, timeout=300,
        )
        response.raise_for_status()

        tmp = tempfile.NamedTemporaryFile(
            suffix=".csv", delete=False, mode="wb",
        )
        bytes_written = 0
        try:
            for chunk in response.iter_content(chunk_size=8192):
                tmp.write(chunk)
                bytes_written += len(chunk)
            tmp.close()
        except Exception:
            tmp.close()
            Path(tmp.name).unlink(missing_ok=True)
            raise

        csv_path = Path(tmp.name)

        self.logger.info(
            "CALC+ CSV download complete: %s (%.1f MB)",
            csv_path, bytes_written / (1024 * 1024),
        )

        if progress_callback:
            progress_callback(bytes_written, "download_complete")

        return csv_path

    # =================================================================
    # Convenience methods
    # =================================================================

    def get_rate_summary(self, keyword, business_size=None):
        """Get min/avg/max rate statistics for a labor category.

        Fetches matching rates and computes summary statistics from the
        current_price field.

        Args:
            keyword: Labor category search term.
            business_size: Not currently filtered server-side (kept for
                           interface compatibility). Filtering is applied
                           client-side if provided.

        Returns:
            dict with keys: keyword, business_size, count, min, avg, max, rates
                rates is the list of all matching rate dicts.
            Returns None if no matching rates found.
        """
        all_rates = list(self.search_rates_all(keyword=keyword))

        # Client-side business_size filter (API ignores the param)
        if business_size is not None:
            bs_upper = business_size.upper()
            all_rates = [
                r for r in all_rates
                if (r.get("business_size") or "").upper() == bs_upper
            ]

        if not all_rates:
            self.logger.info(
                "No rates found for keyword=%r, size=%s",
                keyword, business_size,
            )
            return None

        prices = []
        for r in all_rates:
            price = r.get("current_price")
            if price is not None:
                try:
                    prices.append(float(price))
                except (ValueError, TypeError):
                    pass

        if not prices:
            self.logger.warning(
                "Found %d rates but none had valid current_price",
                len(all_rates),
            )
            return None

        summary = {
            "keyword": keyword,
            "business_size": business_size,
            "count": len(prices),
            "min": round(min(prices), 2),
            "avg": round(sum(prices) / len(prices), 2),
            "max": round(max(prices), 2),
            "rates": all_rates,
        }
        self.logger.info(
            "Rate summary for %r (size=%s): count=%d min=$%.2f avg=$%.2f max=$%.2f",
            keyword, business_size, summary["count"],
            summary["min"], summary["avg"], summary["max"],
        )
        return summary
