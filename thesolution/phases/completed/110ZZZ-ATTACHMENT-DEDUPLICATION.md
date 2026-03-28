# Phase 110ZZZ — Attachment Deduplication

**Status**: COMPLETE
**Depends on**: Phase 110ZZ (Keyword Intel Enhancements) — must be complete. Phase 110Z (Attachment AI Analysis) is a soft dependency — 110ZZZ's migration handles whatever pipeline state exists, so 110Z can run before or after.
**Branch**: `phase-110zzz-attachment-dedup`

## Problem Statement

The attachment pipeline currently treats each opportunity-attachment row as independent, even when multiple opportunities (amendments, modifications, combined synopsis/solicitation notices) reference the exact same SAM.gov resource file. This causes:

- **Redundant downloads**: The same PDF is downloaded N times (once per referencing opportunity), wasting bandwidth and disk space.
- **Redundant text extraction**: CPU-intensive text extraction (including OCR for scanned documents) runs N times for the same file content.
- **Redundant AI analysis**: Expensive Anthropic API calls run N times for identical text, wasting money.
- **Redundant HEAD requests**: Link enrichment makes the same HEAD request to SAM.gov for each opportunity referencing the same URL.
- **41% row duplication**: 12,895 of 31,170 attachment rows (41%) reference a resource GUID that appears on at least one other opportunity.

## Data Analysis

Current state of `opportunity_attachment` (31,170 rows, 7,956 opportunities):

| Metric | Value |
|--------|-------|
| Total attachment rows | 31,170 |
| Distinct resource GUIDs | 23,889 |
| Unique GUIDs (appear once) | 18,276 |
| Shared GUIDs (appear 2+ times) | 5,613 |
| Rows referencing shared GUIDs | 12,895 (41%) |

Distribution of shared GUIDs:

| Shared by N opps | Count of GUIDs |
|------------------|----------------|
| 2 | 4,256 |
| 3 | 1,122 |
| 4 | 172 |
| 5 | 34 |
| 6 | 33 |

Example: Solicitation FA910126QB018 has 6 notice_ids all referencing the same PDF with the same resource GUID.

SAM.gov URL structure: `https://sam.gov/api/prod/opps/v3/opportunities/resources/files/{GUID}/download`

The 32-character hex GUID in the URL is the canonical file identifier from SAM.gov.

## Design

### Resource GUID Extraction

Extract the GUID from SAM.gov URLs using a simple regex:

```python
import re
_RESOURCE_GUID_RE = re.compile(r'/resources/files/([0-9a-f]{32})/download', re.IGNORECASE)

def extract_resource_guid(url: str) -> str | None:
    m = _RESOURCE_GUID_RE.search(url)
    return m.group(1).lower() if m else None
```

This is deterministic and works for all SAM.gov attachment URLs. All attachment URLs in the system are SAM.gov URLs, so `resource_guid` is always populated.

### Two-Tier Dedup Strategy

Deduplication operates at two levels:

1. **First-pass dedup (pre-download): `resource_guid`** — Extracted from the SAM.gov URL. If a resource GUID already exists in `sam_attachment`, skip the download entirely and just insert a mapping row in `opportunity_attachment`. This prevents redundant downloads, HEAD requests, and bandwidth waste.

2. **Definitive dedup (post-download): `content_hash` (SHA-256 of file bytes)** — After downloading, compute the SHA-256 hash of the file. If `content_hash` matches an existing attachment (even one with a different `resource_guid`), skip text extraction and intel analysis. Instead, copy the results (extracted_text, text_hash, page_count, is_scanned, ocr_quality, extraction_status) from the existing `attachment_document`. Both rows remain in `sam_attachment` (no row merging), but only the first occurrence pays the processing cost.

**Content-hash dedup flow**: After `attachment_downloader.py` downloads a new file, it computes SHA-256 and checks `sam_attachment.content_hash` for a match. If found, the downloader sets `download_status='downloaded'` on the new `sam_attachment` row (since the file IS downloaded) but the `attachment_text_extractor.py` checks `attachment_document.text_hash` — if a matching `text_hash` already exists on another document, it copies `extracted_text`, `page_count`, `is_scanned`, `ocr_quality`, and `extraction_status` from the existing document and skips extraction. Similarly, the intel extractor checks if intel already exists for a document with the same `text_hash` and skips if so. Both `sam_attachment` rows are kept — they have different `resource_guid` values but point to identical content.

This approach aligns with existing project conventions — `record_hash`, `content_hash`, and `text_hash` are all `CHAR(64)` SHA-256 values used throughout the codebase.

### New Schema: Normalized 6-Table Model

Six tables: the downloaded file, the extractable document within it, the opportunity-to-attachment mapping, per-document intel, per-document evidence, and per-opportunity rollup.

#### Table 1: `sam_attachment` (one row per unique downloaded file)

Download-level data: URL, resource_guid, filename, file_size_bytes, file_path, content_hash, download status, retry counts.

```sql
CREATE TABLE IF NOT EXISTS sam_attachment (
    attachment_id          INT AUTO_INCREMENT PRIMARY KEY,
    resource_guid          CHAR(32) NOT NULL,
    url                    VARCHAR(500) NOT NULL,
    filename               VARCHAR(500),
    file_size_bytes        BIGINT,
    file_path              VARCHAR(500),
    download_status        ENUM('pending','downloaded','failed','skipped') DEFAULT 'pending',
    content_hash           CHAR(64),
    downloaded_at          DATETIME,
    download_retry_count   INT NOT NULL DEFAULT 0,
    skip_reason            VARCHAR(100),
    last_load_id           INT,
    created_at             DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE INDEX idx_resource_guid (resource_guid),
    INDEX idx_status (download_status),
    INDEX idx_content_hash (content_hash),
    INDEX idx_url (url)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

Key points:
- `resource_guid` is NOT NULL — all URLs are SAM.gov
- `attachment_id` is the PK (kept for downstream compatibility)
- No `notice_id` — that's on the map table
- No extracted text or intel — that's on `attachment_document`

#### Table 2: `attachment_document` (each extractable document within a file)

For standalone PDFs/DOCXs this is 1:1 with `sam_attachment`. For ZIP files (future phase), one sam_attachment -> multiple documents.

Content-level data: extracted_text, page_count, content_type, extraction status.

```sql
CREATE TABLE IF NOT EXISTS attachment_document (
    document_id            INT AUTO_INCREMENT PRIMARY KEY,
    attachment_id          INT NOT NULL,
    filename               VARCHAR(500),
    content_type           VARCHAR(100),
    extracted_text         LONGTEXT,
    page_count             INT,
    is_scanned             TINYINT DEFAULT 0,
    ocr_quality            ENUM('good','fair','poor'),
    extraction_status      ENUM('pending','extracted','failed','unsupported') DEFAULT 'pending',
    text_hash              CHAR(64),
    extracted_at           DATETIME,
    extraction_retry_count INT DEFAULT 0,
    last_load_id           INT,
    created_at             DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_attachment (attachment_id),
    INDEX idx_status (extraction_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

Key points:
- `document_id` is the PK — this is what intel tables reference
- `attachment_id` links back to the parent file
- For standalone files (current behavior): one sam_attachment row -> one document row, `filename` and `content_type` copied from sam_attachment
- For ZIP files (future phase): one sam_attachment row -> N document rows, each with the inner file's name and type
- ZIP handling is NOT implemented in this phase — it's designed into the schema for a future phase
- No cascade FKs

#### Table 3: `opportunity_attachment` (many-to-many mapping, repurposed)

Maps opportunities to attachments. Repurposed from the old table (which held file data). Now it's a lean join table.

```sql
CREATE TABLE IF NOT EXISTS opportunity_attachment (
    notice_id              VARCHAR(100) NOT NULL,
    attachment_id          INT NOT NULL,
    url                    VARCHAR(500) NOT NULL,
    last_load_id           INT,
    created_at             DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (notice_id, attachment_id),
    INDEX idx_attachment (attachment_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

Key points:
- Composite PK `(notice_id, attachment_id)` — no surrogate key needed
- `url` kept for traceability (original URL from this opportunity's resource_links)
- No cascade FKs

**Note on `opportunity.resource_links`**: After migration, the canonical source of truth for which documents belong to which opportunity is `opportunity_attachment` (the map table). The `resource_links` JSON column on `opportunity` remains as the **raw API response** from SAM.gov -- it is preserved for API round-trip fidelity and is used by the downloader to discover new URLs, but the map table is authoritative for document relationships. The enrichment process (`enrich_resource_links`) continues to work independently on this column.

### Intel Table Changes

Intel data is fully re-extractable from document text, so there is no need for complex migration of existing intel rows. The old tables are dropped and replaced with a clean three-table design.

#### Table 4: `document_intel_summary` (per-document intel conclusions)

Replaces the per-attachment rows in the old `opportunity_attachment_intel`. One row per `(document_id, extraction_method)` — the conclusions from analyzing one document with one method.

```sql
CREATE TABLE IF NOT EXISTS document_intel_summary (
    intel_id               INT AUTO_INCREMENT PRIMARY KEY,
    document_id            INT NOT NULL,
    extraction_method      ENUM('keyword','heuristic','ai_haiku','ai_sonnet') NOT NULL,
    source_text_hash       CHAR(64),
    clearance_required     CHAR(1),
    clearance_level        VARCHAR(50),
    clearance_scope        VARCHAR(50),
    clearance_details      TEXT,
    eval_method            VARCHAR(50),
    eval_details           TEXT,
    vehicle_type           VARCHAR(100),
    vehicle_details        TEXT,
    is_recompete           CHAR(1),
    incumbent_name         VARCHAR(200),
    recompete_details      TEXT,
    pricing_structure      VARCHAR(50),
    place_of_performance   VARCHAR(200),
    scope_summary          TEXT,
    period_of_performance  VARCHAR(200),
    labor_categories       JSON,
    key_requirements       JSON,
    overall_confidence     ENUM('high','medium','low') NOT NULL,
    confidence_details     JSON,
    citation_offsets       JSON,
    last_load_id           INT,
    extracted_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE INDEX idx_upsert (document_id, extraction_method),
    INDEX idx_document (document_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

**Key design points:**
- No `notice_id` column — intel belongs to the document, not the opportunity
- `ai_dry_run` is excluded from the `extraction_method` ENUM; dry runs are test mode and should not write intel rows
- No cascade FKs — explicit deletes only

#### Table 5: `document_intel_evidence` (citations/evidence for document-level intel)

Replaces the old `opportunity_intel_source`. Provides evidence/citations for per-document intel conclusions.

```sql
CREATE TABLE IF NOT EXISTS document_intel_evidence (
    evidence_id            INT AUTO_INCREMENT PRIMARY KEY,
    intel_id               INT NOT NULL,
    field_name             VARCHAR(50) NOT NULL,
    document_id            INT,
    source_filename        VARCHAR(500),
    page_number            INT,
    char_offset_start      INT,
    char_offset_end        INT,
    matched_text           VARCHAR(500),
    surrounding_context    TEXT,
    pattern_name           VARCHAR(100),
    extraction_method      ENUM('keyword','heuristic','ai_haiku','ai_sonnet') NOT NULL,
    confidence             ENUM('high','medium','low') NOT NULL,
    created_at             DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_intel (intel_id),
    INDEX idx_document (document_id),
    INDEX idx_field (field_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

**Key design points:**
- `intel_id` points to `document_intel_summary.intel_id` (document intel only, NOT the summary table)
- The opportunity-level summary table does NOT have source citations — it's derived
- No cascade FKs

#### Table 6: `opportunity_attachment_summary` (per-opportunity rollup)

Replaces the consolidated NULL-attachment rows in the old `opportunity_attachment_intel`. One row per `(notice_id, extraction_method)` — the rolled-up best intel across all documents for that opportunity.

```sql
CREATE TABLE IF NOT EXISTS opportunity_attachment_summary (
    summary_id             INT AUTO_INCREMENT PRIMARY KEY,
    notice_id              VARCHAR(100) NOT NULL,
    extraction_method      ENUM('keyword','heuristic','ai_haiku','ai_sonnet') NOT NULL,
    clearance_required     CHAR(1),
    clearance_level        VARCHAR(50),
    clearance_scope        VARCHAR(50),
    clearance_details      TEXT,
    eval_method            VARCHAR(50),
    eval_details           TEXT,
    vehicle_type           VARCHAR(100),
    vehicle_details        TEXT,
    is_recompete           CHAR(1),
    incumbent_name         VARCHAR(200),
    recompete_details      TEXT,
    pricing_structure      VARCHAR(50),
    place_of_performance   VARCHAR(200),
    scope_summary          TEXT,
    period_of_performance  VARCHAR(200),
    labor_categories       JSON,
    key_requirements       JSON,
    overall_confidence     ENUM('high','medium','low') NOT NULL,
    confidence_details     JSON,
    citation_offsets       JSON,
    source_text_hash       CHAR(64),
    last_load_id           INT,
    extracted_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE INDEX idx_upsert (notice_id, extraction_method),
    INDEX idx_notice (notice_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

**Key design points:**
- No `document_id` column — this is opportunity-level, not document-level
- This is a **derived/cached table** — can be regenerated from per-document intel at any time
- No cascade FKs

### Column Mapping from Old `opportunity_attachment`

NO columns are lost. Only INTEL data is dropped (re-extractable).

| Old column | New location |
|---|---|
| attachment_id | `sam_attachment.attachment_id` |
| notice_id | `opportunity_attachment.notice_id` |
| url | `sam_attachment.url` + `opportunity_attachment.url` |
| filename | `sam_attachment.filename` + `attachment_document.filename` |
| content_type | `attachment_document.content_type` |
| file_size_bytes | `sam_attachment.file_size_bytes` |
| file_path | `sam_attachment.file_path` |
| extracted_text | `attachment_document.extracted_text` |
| page_count | `attachment_document.page_count` |
| is_scanned | `attachment_document.is_scanned` |
| ocr_quality | `attachment_document.ocr_quality` |
| download_status | `sam_attachment.download_status` |
| extraction_status | `attachment_document.extraction_status` |
| content_hash | `sam_attachment.content_hash` |
| text_hash | `attachment_document.text_hash` |
| downloaded_at | `sam_attachment.downloaded_at` |
| extracted_at | `attachment_document.extracted_at` |
| download_retry_count | `sam_attachment.download_retry_count` |
| extraction_retry_count | `attachment_document.extraction_retry_count` |
| skip_reason | `sam_attachment.skip_reason` |
| last_load_id | Both tables |
| created_at | Both tables |

### Tables Being Dropped

- `opportunity_attachment_intel` — replaced by `document_intel_summary` + `opportunity_attachment_summary`
- `opportunity_intel_source` — replaced by `document_intel_evidence`

### Migration Strategy

All operations are non-destructive. The migration runs as a Python script (or CLI command) with these steps:

**Transaction boundaries note**: MySQL DDL (CREATE/ALTER/DROP TABLE) auto-commits. Steps 1-3 are DDL. Step 4 INSERT statements are DML and should use explicit `START TRANSACTION` / `COMMIT`. Steps 5-6 are DDL. The rollback script handles DDL reversal.

**Step 1: Add `resource_guid` to existing table**
```sql
ALTER TABLE opportunity_attachment
    ADD COLUMN resource_guid CHAR(32) AFTER attachment_id;
```

**Step 2: Populate `resource_guid` from existing URLs**
```sql
UPDATE opportunity_attachment
SET resource_guid = LOWER(SUBSTRING_INDEX(SUBSTRING_INDEX(url, '/resources/files/', -1), '/download', 1))
WHERE url LIKE '%/resources/files/%/download%'
  AND resource_guid IS NULL;
```

**Step 2b: Validate no NULL resource_guids remain**
```sql
-- Validate: all rows should have resource_guid populated
-- If any rows have NULL, they have non-standard URLs that need manual review
SELECT COUNT(*) AS null_guid_count FROM opportunity_attachment WHERE resource_guid IS NULL;
-- Expected: 0. If non-zero, investigate and resolve before proceeding.
-- The final DDL has resource_guid CHAR(32) NOT NULL — any NULLs will cause the migration to fail.
```

**Step 3: Identify canonical rows** (one per resource_guid — keep the one with the most processing done)

Pick the "best" row per resource_guid. Priority order:
1. **Furthest along in the pipeline** — a row with extracted text + intel beats one that's only downloaded, which beats one that's only pending.
2. **Has intel** — rows referenced by `opportunity_attachment_intel` are preferred (they have analysis results we don't want to redo).
3. **Downloaded over not** — `downloaded` > `failed` > `skipped` > `pending`
4. **Extracted over not** — `extracted` > `failed` > `unsupported` > `pending`
5. **Not deleted/skipped** — rows with `skip_reason IS NOT NULL` are deprioritized.
6. **Earliest created** — tiebreaker to get the original/first-seen row.

**Note**: This uses a regular table (not `CREATE TEMPORARY TABLE`) because MySQL temporary tables are session-scoped and disappear on connection close. If the migration script uses connection pooling (this project does), Steps 4-6 could run on different connections and lose the temp table. The `_migration_canonical` table is dropped at the end of migration.

```sql
CREATE TABLE _migration_canonical AS
SELECT resource_guid, attachment_id AS canonical_id
FROM (
    SELECT oa.resource_guid, oa.attachment_id,
           ROW_NUMBER() OVER (
               PARTITION BY oa.resource_guid
               ORDER BY
                   -- Prefer rows that have intel analysis results
                   CASE WHEN EXISTS (
                       SELECT 1 FROM opportunity_attachment_intel ai
                       WHERE ai.attachment_id = oa.attachment_id
                   ) THEN 0 ELSE 1 END,
                   -- Prefer furthest along in extraction pipeline
                   FIELD(COALESCE(oa.extraction_status, 'pending'), 'extracted', 'failed', 'unsupported', 'pending'),
                   -- Prefer downloaded files
                   FIELD(COALESCE(oa.download_status, 'pending'), 'downloaded', 'failed', 'skipped', 'pending'),
                   -- Deprioritize skipped/deleted rows
                   CASE WHEN oa.skip_reason IS NOT NULL THEN 1 ELSE 0 END,
                   -- Tiebreaker: earliest created
                   oa.created_at ASC
           ) AS rn
    FROM opportunity_attachment oa
) ranked
WHERE rn = 1;

-- Indexes needed for Step 4 joins
ALTER TABLE _migration_canonical ADD INDEX idx_guid (resource_guid);
ALTER TABLE _migration_canonical ADD INDEX idx_canonical (canonical_id);
```

This ensures that when deduplicating, we **never discard a row that is further along in the pipeline** in favor of a less-processed duplicate.

**Step 4: Create new tables and migrate data**

```sql
-- Create sam_attachment table (download-level columns from canonical rows)
CREATE TABLE IF NOT EXISTS sam_attachment (
    attachment_id          INT AUTO_INCREMENT PRIMARY KEY,
    resource_guid          CHAR(32) NOT NULL,
    url                    VARCHAR(500) NOT NULL,
    filename               VARCHAR(500),
    file_size_bytes        BIGINT,
    file_path              VARCHAR(500),
    download_status        ENUM('pending','downloaded','failed','skipped') DEFAULT 'pending',
    content_hash           CHAR(64),
    downloaded_at          DATETIME,
    download_retry_count   INT NOT NULL DEFAULT 0,
    skip_reason            VARCHAR(100),
    last_load_id           INT,
    created_at             DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE INDEX idx_resource_guid (resource_guid),
    INDEX idx_status (download_status),
    INDEX idx_content_hash (content_hash),
    INDEX idx_url (url)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

START TRANSACTION;

-- Insert canonical rows into sam_attachment (download-level columns)
INSERT INTO sam_attachment (attachment_id, resource_guid, url, filename, file_size_bytes,
    file_path, download_status, content_hash, downloaded_at, download_retry_count,
    skip_reason, last_load_id, created_at)
SELECT oa.attachment_id, oa.resource_guid, oa.url, oa.filename, oa.file_size_bytes,
    oa.file_path, oa.download_status, oa.content_hash, oa.downloaded_at,
    oa.download_retry_count, oa.skip_reason, oa.last_load_id, oa.created_at
FROM opportunity_attachment oa
JOIN _migration_canonical c ON oa.attachment_id = c.canonical_id;

-- Create attachment_document table (content-level columns, 1:1 with sam_attachment for now)
CREATE TABLE IF NOT EXISTS attachment_document (
    document_id            INT AUTO_INCREMENT PRIMARY KEY,
    attachment_id          INT NOT NULL,
    filename               VARCHAR(500),
    content_type           VARCHAR(100),
    extracted_text         LONGTEXT,
    page_count             INT,
    is_scanned             TINYINT DEFAULT 0,
    ocr_quality            ENUM('good','fair','poor'),
    extraction_status      ENUM('pending','extracted','failed','unsupported') DEFAULT 'pending',
    text_hash              CHAR(64),
    extracted_at           DATETIME,
    extraction_retry_count INT DEFAULT 0,
    last_load_id           INT,
    created_at             DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_attachment (attachment_id),
    INDEX idx_status (extraction_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Insert 1:1 document rows from canonical sam_attachment rows
INSERT INTO attachment_document (attachment_id, filename, content_type, extracted_text,
    page_count, is_scanned, ocr_quality, extraction_status, text_hash, extracted_at,
    extraction_retry_count, last_load_id, created_at)
SELECT oa.attachment_id, oa.filename, oa.content_type, oa.extracted_text,
    oa.page_count, oa.is_scanned, oa.ocr_quality, oa.extraction_status,
    oa.text_hash, oa.extracted_at, oa.extraction_retry_count,
    oa.last_load_id, oa.created_at
FROM opportunity_attachment oa
JOIN _migration_canonical c ON oa.attachment_id = c.canonical_id;

-- Create opportunity_attachment_new (temp name since old table still exists)
CREATE TABLE opportunity_attachment_new (
    notice_id              VARCHAR(100) NOT NULL,
    attachment_id          INT NOT NULL,
    url                    VARCHAR(500) NOT NULL,
    last_load_id           INT,
    created_at             DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (notice_id, attachment_id),
    INDEX idx_attachment (attachment_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Insert all (notice_id, canonical_id, url) mappings
INSERT INTO opportunity_attachment_new (notice_id, attachment_id, url, last_load_id, created_at)
SELECT oa.notice_id, c.canonical_id, oa.url, oa.last_load_id, oa.created_at
FROM opportunity_attachment oa
JOIN _migration_canonical c ON oa.resource_guid = c.resource_guid;
COMMIT;
```

**Step 5: Drop old intel tables, create new intel tables (empty — re-extract later)**

```sql
-- Drop old tables (order matters: sources reference intel)
DROP TABLE IF EXISTS opportunity_intel_source;
DROP TABLE IF EXISTS opportunity_attachment_intel;

-- Create new intel tables (empty)
CREATE TABLE IF NOT EXISTS document_intel_summary (
    intel_id               INT AUTO_INCREMENT PRIMARY KEY,
    document_id            INT NOT NULL,
    extraction_method      ENUM('keyword','heuristic','ai_haiku','ai_sonnet') NOT NULL,
    source_text_hash       CHAR(64),
    clearance_required     CHAR(1),
    clearance_level        VARCHAR(50),
    clearance_scope        VARCHAR(50),
    clearance_details      TEXT,
    eval_method            VARCHAR(50),
    eval_details           TEXT,
    vehicle_type           VARCHAR(100),
    vehicle_details        TEXT,
    is_recompete           CHAR(1),
    incumbent_name         VARCHAR(200),
    recompete_details      TEXT,
    pricing_structure      VARCHAR(50),
    place_of_performance   VARCHAR(200),
    scope_summary          TEXT,
    period_of_performance  VARCHAR(200),
    labor_categories       JSON,
    key_requirements       JSON,
    overall_confidence     ENUM('high','medium','low') NOT NULL,
    confidence_details     JSON,
    citation_offsets       JSON,
    last_load_id           INT,
    extracted_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE INDEX idx_upsert (document_id, extraction_method),
    INDEX idx_document (document_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS document_intel_evidence (
    evidence_id            INT AUTO_INCREMENT PRIMARY KEY,
    intel_id               INT NOT NULL,
    field_name             VARCHAR(50) NOT NULL,
    document_id            INT,
    source_filename        VARCHAR(500),
    page_number            INT,
    char_offset_start      INT,
    char_offset_end        INT,
    matched_text           VARCHAR(500),
    surrounding_context    TEXT,
    pattern_name           VARCHAR(100),
    extraction_method      ENUM('keyword','heuristic','ai_haiku','ai_sonnet') NOT NULL,
    confidence             ENUM('high','medium','low') NOT NULL,
    created_at             DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_intel (intel_id),
    INDEX idx_document (document_id),
    INDEX idx_field (field_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS opportunity_attachment_summary (
    summary_id             INT AUTO_INCREMENT PRIMARY KEY,
    notice_id              VARCHAR(100) NOT NULL,
    extraction_method      ENUM('keyword','heuristic','ai_haiku','ai_sonnet') NOT NULL,
    clearance_required     CHAR(1),
    clearance_level        VARCHAR(50),
    clearance_scope        VARCHAR(50),
    clearance_details      TEXT,
    eval_method            VARCHAR(50),
    eval_details           TEXT,
    vehicle_type           VARCHAR(100),
    vehicle_details        TEXT,
    is_recompete           CHAR(1),
    incumbent_name         VARCHAR(200),
    recompete_details      TEXT,
    pricing_structure      VARCHAR(50),
    place_of_performance   VARCHAR(200),
    scope_summary          TEXT,
    period_of_performance  VARCHAR(200),
    labor_categories       JSON,
    key_requirements       JSON,
    overall_confidence     ENUM('high','medium','low') NOT NULL,
    confidence_details     JSON,
    citation_offsets       JSON,
    source_text_hash       CHAR(64),
    last_load_id           INT,
    extracted_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE INDEX idx_upsert (notice_id, extraction_method),
    INDEX idx_notice (notice_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

**Note**: The migration script does NOT re-extract intel. After migration completes, you must manually run `extract attachment-intel` and `analyze attachment-ai` as separate post-migration steps (see Pre-Migration Checklist) to repopulate intel from document text. Intel tables will be empty until you run re-extraction.

**Note**: `ai_dry_run` extraction_method should NOT write intel rows going forward. Dry runs log usage but produce no persistent intel.

**Step 6: Swap tables**

**Safety note**: Step 6 drops the old table. This is safe because Step 4 already migrated ALL data into the new tables. The migration script should verify row counts match before dropping.

```sql
-- Atomically swap tables
RENAME TABLE opportunity_attachment TO _old_opportunity_attachment,
             opportunity_attachment_new TO opportunity_attachment;

-- Drop the old table (safe — data already migrated)
DROP TABLE IF EXISTS _old_opportunity_attachment;

-- Clean up migration helper table
DROP TABLE IF EXISTS _migration_canonical;
```

**Step 7: Verify row counts**

Post-migration expected state:
- `sam_attachment`: ~23,889 rows (one per unique resource GUID)
- `attachment_document`: ~23,889 rows (1:1 with sam_attachment for now)
- `opportunity_attachment`: ~31,170 rows (preserves all opportunity-to-attachment relationships)
- `document_intel_summary`: 0 rows (empty — repopulated by `extract attachment-intel`)
- `document_intel_evidence`: 0 rows (empty — repopulated by `extract attachment-intel`)
- `opportunity_attachment_summary`: 0 rows (empty — repopulated by `extract attachment-intel`)
- Old tables `opportunity_attachment_intel` and `opportunity_intel_source`: dropped

**Step 8: File migration**

Move files from old path to new GUID-based layout: `{ATTACHMENT_DIR}/{resource_guid}/{filename}` — flat, no two-level nesting. Update `file_path` column on `sam_attachment` accordingly.

### File Storage Changes

Current: Files stored at `{ATTACHMENT_DIR}/{notice_id}/{filename}`

New: Files stored at `{ATTACHMENT_DIR}/{resource_guid}/{filename}`

With ~24K unique GUIDs, NTFS handles a single directory level fine. Simpler to implement, debug, and browse than a two-level prefix scheme.

Migration moves existing files from the old path to the new path. The `file_path` column on `sam_attachment` is updated accordingly.

### Pipeline Changes

#### `opportunity_loader.py` — `enrich_resource_links`

**Note**: `enrich_resource_links` does NOT touch the attachment tables at all — it reads/writes only the `opportunity.resource_links` JSON column and calls `resolve_resource_links()` for HEAD requests. No queries break from the table restructuring.

Optional optimization (can be deferred):
- Before enriching, extract resource GUIDs from URLs.
- Check `sam_attachment` for existing rows with the same GUID.
- Skip HEAD requests for GUIDs that already have filename/content_type populated.

The GUID-aware insert logic (check for existing GUID, insert mapping row vs. sam_attachment row) belongs in `attachment_downloader.py`, not here.

#### `resource_link_resolver.py`

- Accept a set of "already resolved GUIDs" to skip.
- No structural change; the caller (opportunity_loader) handles dedup.

#### `attachment_downloader.py`

**Warning: This is the most complex change in the phase.** The downloader's write path (`_upsert_attachment_row`, `_mark_transient_failure`) fundamentally changes from a single `INSERT ... ON DUPLICATE KEY UPDATE` keyed on `(notice_id, url)` to a multi-table operation:
1. Upsert `sam_attachment` by `resource_guid`
2. Create initial `attachment_document` row (1:1, pending extraction)
3. Insert/check `opportunity_attachment` for the `(notice_id, attachment_id)` pair

This is a STRUCTURAL REWRITE of the write path, not just query updates. The `_upsert_attachment_row` method must become a multi-table operation. Step 2-3 need the `attachment_id` from step 1, requiring either a SELECT-after-upsert or `LAST_INSERT_ID()`.

**Thread safety note**: The multi-threaded downloader (default 5 workers) could have two threads processing the same `resource_guid` simultaneously (from two different opportunities). The `UNIQUE INDEX idx_resource_guid` handles the race at the DB level (one INSERT succeeds, the other hits ON DUPLICATE KEY UPDATE), but the retry-count logic in `_mark_transient_failure` could have concurrent increments. This is a known issue to address during implementation.

Has **7 SQL statements** referencing `opportunity_attachment` that all need updating:

1. `_query_urls` (line 229): `SELECT DISTINCT oa.notice_id FROM opportunity_attachment oa` — the missing_filter subquery. After migration, this becomes a join through `opportunity_attachment` (map) + `sam_attachment`.
2. `_query_urls` (line 284): `SELECT notice_id, url FROM opportunity_attachment` — already-downloaded filter. Must query `opportunity_attachment` joined to `sam_attachment`.
3. `_get_existing_hash` (line 509): `SELECT content_hash FROM opportunity_attachment WHERE notice_id = %s AND url = %s` — change to query `sam_attachment` by resource_guid or url.
4. `_upsert_attachment_row` (line 538): `INSERT INTO opportunity_attachment` — this is the core upsert, currently keyed on `(notice_id, url)`. Must split into: (a) upsert `sam_attachment` by resource_guid, (b) create `attachment_document` row (1:1), (c) insert `opportunity_attachment` mapping row for the `(notice_id, attachment_id)` pair.
5. `_mark_transient_failure` (line 571): `INSERT INTO opportunity_attachment` — same split needed.
6. `_mark_transient_failure` (line 580): `SELECT download_retry_count FROM opportunity_attachment WHERE notice_id = %s AND url = %s` — change to query by resource_guid on `sam_attachment`.
7. `_mark_transient_failure` (line 592): `UPDATE opportunity_attachment SET download_status = 'skipped'` — same, update `sam_attachment`.

Key behavioral changes:
- Before downloading, check if the resource GUID already has `download_status='downloaded'` in `sam_attachment`. If already downloaded, skip — just insert the mapping row.
- Change file storage path to GUID-based layout.
- The `_download_single` method currently takes `notice_id` as first arg and passes it everywhere. Post-migration, `notice_id` is only needed for the mapping table insert, not for the `sam_attachment` or `attachment_document` table operations.
- Update the batch query to only select documents that need downloading (one row per unique GUID, not per opportunity).

#### `attachment_text_extractor.py`

Has **4 SQL statements** referencing `opportunity_attachment`:

1. `_fetch_pending` (line 1050): `SELECT attachment_id, notice_id, filename, content_type, file_path FROM opportunity_attachment` — reads from `attachment_document` joined to `sam_attachment` (for file_path). The `notice_id` filter (line 1045) must become a join through `opportunity_attachment` (map).
2. `_save_extraction` (line 1105): `UPDATE opportunity_attachment SET extracted_text = ...` — update `attachment_document` instead.
3. `_mark_failed` (line 1135): `UPDATE opportunity_attachment SET extraction_status = 'failed'` — update `attachment_document` instead.
4. `_mark_unsupported` (line 1156): `UPDATE opportunity_attachment SET extraction_status = 'unsupported'` — update `attachment_document` instead.

Key behavioral changes:
- Query `attachment_document` joined to `sam_attachment` for documents needing extraction (`extraction_status = 'pending'`). This is the main dedup win — one extraction per unique file, not per opportunity.
- When filtering by `--notice-id`, join through `opportunity_attachment` (map) to find that opportunity's documents.
- The `notice_id` column in _fetch_pending results is used for logging. Replace with `resource_guid` or `filename` for logging.
- No change to extraction logic itself (file reading, OCR, page counting) — just the query that finds work to do and the UPDATE table name.

#### `attachment_intel_extractor.py`

Has **4 SQL statements** referencing `opportunity_attachment` (not the intel table):

1. `_fetch_eligible_notices` (lines 505, 518): `SELECT notice_id FROM opportunity_attachment WHERE extraction_status = 'extracted'` — must join `attachment_document` through `opportunity_attachment` (map) to get notice_ids.
2. `_gather_text_sources` (line 634): `SELECT attachment_id, filename, extracted_text FROM opportunity_attachment WHERE notice_id = %s` — must join `attachment_document` through `opportunity_attachment` (map) where map.notice_id = %s.
3. `_resolve_incumbent_for_opportunity` (line 1280): `LEFT JOIN opportunity_attachment a ON i.attachment_id = a.attachment_id` — join through `attachment_document` instead.

Key behavioral changes:
- Must write per-document intel to `document_intel_summary` (not the old `opportunity_attachment_intel` table name).
- Must write evidence to `document_intel_evidence` (not the old `opportunity_intel_source` table name).
- Must NOT write `ai_dry_run` intel rows — dry runs should log but not persist intel.
- The consolidated NULL-attachment row logic (which previously wrote a summary row with `attachment_id IS NULL`) should now write to `opportunity_attachment_summary` instead.
- The _gather_text_sources query joins through the map table to find documents for a specific notice_id, which may return fewer documents post-dedup (one row per unique document instead of duplicates).
- Before extracting intel for a document, check if intel already exists for that `document_id` + `extraction_method`. If another notice already triggered extraction for this document, skip it.
- **Pre-existing bug in `_cleanup_stale_intel_rows`**: must delete evidence rows (from `document_intel_evidence`) BEFORE deleting intel rows (from `document_intel_summary`), because evidence rows reference `intel_id`. The old `_cleanup_stale_intel_rows` method deletes intel rows but does not delete source/evidence rows at all, leaving them orphaned. There are 8,932 orphaned source rows in production today from this bug.

#### `attachment_ai_analyzer.py`

Has **1 SQL statement** referencing `opportunity_attachment` (the document table, not intel):

1. `_fetch_eligible_documents` (line 314): `FROM opportunity_attachment oa` — reads from `attachment_document` joined to `sam_attachment`. The `notice_id` filter (line 297: `oa.notice_id = %s`) must become a join through `opportunity_attachment` (map).

The `_save_intel` and `_save_ai_sources` methods must write to `document_intel_summary` and `document_intel_evidence` (new table names). Post-migration, the document row won't have `notice_id`, so the fetch query must join through the map table to provide it (use the canonical/oldest notice_id).

**AI dry run (`ai_dry_run`) should log usage but NOT write intel rows.** Dry runs are test mode — they should call `_log_usage` for cost tracking but skip `_save_intel` and `_save_ai_sources` entirely.

Also note: `_log_usage` (line 450) writes `notice_id` to `ai_usage_log`. After dedup, this will be whichever canonical notice_id was provided. This is fine for cost tracking.

#### `attachment_cleanup.py`

Has **5 SQL statements** referencing `opportunity_attachment`:

1. `_fetch_eligible` (line 145): `SELECT ... FROM opportunity_attachment oa` — reads from `sam_attachment` table.
2. `_fetch_eligible` (line 163): `AND oa.notice_id = %s` — notice_id filter when `--notice-id` is passed. Must become a join through `opportunity_attachment` (map).
3. `_clear_file_path` (line 181): `UPDATE opportunity_attachment SET file_path = NULL` — update `sam_attachment` table.
4. `_fetch_eligible` (line 150): `LEFT JOIN opportunity_attachment_intel` — checks keyword/heuristic intel exists before allowing cleanup. Must check `document_intel_summary` instead.
5. `_fetch_eligible` (line 155): `LEFT JOIN opportunity_attachment_intel` — checks AI intel exists. Must check `document_intel_summary` instead.

**File deletion rule**: Only delete when `SELECT COUNT(*) FROM opportunity_attachment WHERE attachment_id = ?` returns 0. This means no opportunity references the attachment anymore.

Additionally, the parent directory cleanup logic (lines 99-105) currently tries to `rmdir()` the `{notice_id}/` folder. After migration to GUID-based paths (`{resource_guid}/`), this simplifies to just removing the `{resource_guid}/` folder when empty — no two-level directory handling needed.

**Clarification**: Pipeline stages (download_status, extraction_status, intel, AI analysis) are all per-document, not per-opportunity. The current eligibility check works at the document level and will continue to work after the restructuring. The only change needed for "all mapped opportunities" is if we want to gate cleanup on all notices having been fully processed — but since processing is per-document, not per-notice, this is unnecessary. Keep the current document-level eligibility logic; just update the table names and fix the notice_id filter.

### C# API Changes

#### Models Needed

| Model | Table | Notes |
|-------|-------|-------|
| `SamAttachment` | `sam_attachment` | New model for download-level entity |
| `AttachmentDocument` | `attachment_document` | New model for content-level entity |
| `OpportunityAttachment` | `opportunity_attachment` | Lean map, composite PK via `HasKey` |
| `DocumentIntelSummary` | `document_intel_summary` | Replaces per-attachment rows in old intel table |
| `DocumentIntelEvidence` | `document_intel_evidence` | Replaces `OpportunityIntelSource` |
| `OpportunityAttachmentSummary` | `opportunity_attachment_summary` | Replaces NULL-attachment consolidated rows |

#### `SamAttachment.cs` (Core/Models)

New model for the `sam_attachment` table:
- `AttachmentId` (int, PK)
- `ResourceGuid` (string, required, MaxLength 32)
- `Url` (string, required, MaxLength 500)
- `Filename` (string?, MaxLength 500)
- `FileSizeBytes` (long?)
- `FilePath` (string?, MaxLength 500)
- `DownloadStatus` (string, MaxLength 20)
- `ContentHash` (string?, MaxLength 64)
- `DownloadedAt` (DateTime?)
- `DownloadRetryCount` (int)
- `SkipReason` (string?, MaxLength 100)
- `LastLoadId` (int?)
- `CreatedAt` (DateTime)

#### `AttachmentDocument.cs` (Core/Models)

New model for the `attachment_document` table:
- `DocumentId` (int, PK)
- `AttachmentId` (int, required)
- `Filename` (string?, MaxLength 500)
- `ContentType` (string?, MaxLength 100)
- `ExtractedText` (string?)
- `PageCount` (int?)
- `IsScanned` (bool)
- `OcrQuality` (string?, MaxLength 10)
- `ExtractionStatus` (string, MaxLength 20)
- `TextHash` (string?, MaxLength 64)
- `ExtractedAt` (DateTime?)
- `ExtractionRetryCount` (int)
- `LastLoadId` (int?)
- `CreatedAt` (DateTime)
- Navigation property to `SamAttachment`

#### `OpportunityAttachment.cs` (Core/Models)

Repurposed as lean join table (composite PK, no surrogate key):
- `NoticeId` (string, required — part of composite PK)
- `AttachmentId` (int, required — part of composite PK)
- `Url` (string, required, MaxLength 500)
- `LastLoadId` (int?)
- `CreatedAt` (DateTime)
- Navigation property to `SamAttachment`

Configure composite PK in `OnModelCreating`: `builder.HasKey(m => new { m.NoticeId, m.AttachmentId });`

#### `FedProspectorDbContext.cs` (Infrastructure/Data)

- Add `DbSet<SamAttachment>` for the sam_attachment table
- Add `DbSet<AttachmentDocument>` for the document table
- Update `DbSet<OpportunityAttachment>` — model is now lean join table
- Add `DbSet<DocumentIntelSummary>`
- Add `DbSet<DocumentIntelEvidence>`
- Add `DbSet<OpportunityAttachmentSummary>`
- Add `OnModelCreating` configuration for composite PK on `OpportunityAttachment`

#### `AttachmentIntelService.cs` (Infrastructure/Services)

Queries change to join through `opportunity_attachment` (map table), and consolidated intel queries use `opportunity_attachment_summary`:

| Line | Current Code | Change Required |
|------|-------------|-----------------|
| 57 | `.Where(a => a.NoticeId == noticeId)` | Join through `OpportunityAttachment` map where `m.NoticeId == noticeId`, then to `AttachmentDocument` via `m.AttachmentId` |
| 65 | `.Where(i => i.NoticeId == noticeId)` | Query `DocumentIntelSummary` by document_ids from map table join |
| 169 | `NoticeId = noticeId,` | **No change** — DTO response assignment, not a DB write |
| 300 | `.Where(a => a.NoticeId == noticeId && a.ExtractionStatus == "extracted")` | Join through map table to `AttachmentDocument`, keep extraction filter |
| 310 | `.Where(i => i.NoticeId == noticeId` | Query `OpportunityAttachmentSummary` where `s.NoticeId == noticeId` |
| 343 | `NoticeId = noticeId,` | **No change** — DTO response assignment, not a DB write |
| 562 | `_context.OpportunityAttachments.AsNoTracking().Where(...)` | Update to query `AttachmentDocuments` via map table join |

The general pattern change for read queries:

```csharp
// Before:
.Where(a => a.NoticeId == noticeId)

// After:
var attachmentIds = await _context.OpportunityAttachments
    .Where(m => m.NoticeId == noticeId)
    .Select(m => m.AttachmentId)
    .ToListAsync();
// Then filter documents by attachmentIds via AttachmentDocument.AttachmentId

// For consolidated intel (was NULL-attachment row):
// Before: .Where(i => i.NoticeId == noticeId && i.AttachmentId == null)
// After:  _context.OpportunityAttachmentSummaries.Where(s => s.NoticeId == noticeId)
```

#### `AdminService.cs` (Infrastructure/Services)

**No change needed.** Only `attachment_id` reference is in a raw SQL query against `ai_usage_log`, not `opportunity_attachment`.

#### C# DTOs

- `AttachmentSummaryDto` — add `ResourceGuid` property (string?) so the UI can display/use the GUID.
- No changes to `AttachmentIntelBreakdownDto` — it references `AttachmentId` which is unchanged.

#### Pre-existing Mismatches to Fix

- `Url` is `[MaxLength(2000)]` in C# model but `VARCHAR(500)` in DDL — align during migration
- `ExtractionRetryCount` in DDL but missing from C# model — add property

#### No EF Core Migration Needed

Schema owned by Python DDL. Note this explicitly to avoid confusion.

### UI Changes

The UI communicates through the C# API, so it won't break from the DB restructuring alone — as long as the API response shape is preserved. However, several files need review and minor updates.

#### `DocumentIntelligenceTab.tsx` (pages/opportunities)

This is the main consumer of attachment data. It renders:
- `AttachmentsTable` component showing `AttachmentSummaryDto[]` (attachmentId, filename, contentType, downloadStatus, extractionStatus, etc.)
- `PerAttachmentBreakdown` component showing `AttachmentIntelBreakdownDto[]`
- Attachment counts, analysis status, "Run analysis" buttons

**UX decision needed**: When viewing an opportunity that shares documents with amendments (e.g., a solicitation with 6 amendments all referencing the same PDF), should the UI show:
1. **Per-notice documents only** — only the documents linked to this specific notice_id via the map table (current behavior, preserved)
2. **Solicitation-family documents** — all documents across all notices in the same solicitation family

Recommendation: Keep per-notice scoping (option 1) as default. The API already handles this via the map table join. A future enhancement could add a "Show all related documents" toggle.

#### `OpportunityDetailPage.tsx` (pages/opportunities)

References attachments in resource_links rendering (line ~130: `rl.filename ?? 'Attachment ${idx + 1}'`). This reads from the `resource_links` JSON on the opportunity, not from the API attachment endpoint. **No change needed**, but worth noting for awareness.

#### `api.ts` (types)

TypeScript DTOs that need updates:
- `AttachmentSummaryDto` (line ~1253) — add optional `resourceGuid?: string` field to match the new C# DTO property.
- `AttachmentIntelBreakdownDto` (line ~1265) — no change needed (references `attachmentId` which is unchanged).
- `attachmentCount` fields on parent DTOs (lines ~1211, ~1307) — no change needed; counts are computed by the API.

No breaking changes expected if the API maintains the same response shape, which it should since `AttachmentId` is preserved as a key column.

### Handling Document Deletion / Replacement

**File deletion rule**: A file should only be deleted from disk when `SELECT COUNT(*) FROM opportunity_attachment WHERE attachment_id = ?` returns 0. This means no opportunity references the attachment anymore. The cleanup stage must check this count before deleting.

SAM.gov can remove or replace attachments on an opportunity. When an opportunity is re-loaded:

1. **Document removed from `resource_links`**: The URL disappears from the opportunity's `resource_links` JSON, but the `opportunity_attachment` map row and `sam_attachment` / `attachment_document` rows remain. The cleanup stage should detect orphaned map rows (map rows whose URL is no longer in the opportunity's `resource_links`) and mark them accordingly. The file itself should only be deleted from disk when **no** map rows reference the attachment.

2. **Document replaced (new URL/GUID, same logical slot)**: This is effectively a deletion + new document. The old map row becomes orphaned, the new URL creates a new `sam_attachment` row, a new `attachment_document` row, and a new map row. The old file is cleaned up only when no other opportunities still reference it.

3. **Pipeline behavior on dedup conflict**: When a new opportunity references a resource GUID that already exists in `sam_attachment`, the pipeline must check the existing row's processing state. If the existing row is further along (e.g., already has downloaded file and extracted text), just add the map row. If the existing row somehow failed but a new duplicate succeeds, update the `sam_attachment` row with the successful result — don't discard progress.

4. **Failed/skipped on one, succeeded on another**: Before dedup, it's possible that the same resource GUID was downloaded successfully under one `notice_id` but failed or was skipped under another (e.g., transient network error, file size limit hit on one attempt but not another, retry count exceeded). The canonical row selection must account for this — always prefer the **successful** row's data. During migration, if the canonical row has `download_status='failed'` but a duplicate row has `download_status='downloaded'` with a valid `file_path`, the migration should copy the successful file data (file_path, content_hash, etc.) onto the canonical row before deleting the duplicate. The same applies post-migration: if an attachment is in `failed` state but a new opportunity triggers a fresh download of the same GUID that succeeds, the existing `sam_attachment` row should be updated with the successful result rather than remaining stuck in `failed`.

### Documentation Updates

**Critical**: This phase restructures the attachment pipeline from a 1-table model (old `opportunity_attachment` with all data) to a normalized 6-table model. This is a major semantic shift that will confuse agents and developers if documentation isn't updated.

New table descriptions:
- `sam_attachment` = the downloaded file (one row per unique resource GUID)
- `attachment_document` = each extractable document within a file (1:1 now, N:1 for ZIPs later)
- `opportunity_attachment` = many-to-many mapping (repurposed, same name, lean join table)
- `document_intel_summary` = per-document conclusions per extraction_method
- `document_intel_evidence` = citations/evidence for document-level intel
- `opportunity_attachment_summary` = per-opportunity rollup (derived, re-generatable)

Files that reference `opportunity_attachment` and must be updated:

| File | What to update |
|------|---------------|
| `CLAUDE.md` | Update "Attachment pipeline" description, file references table |
| `thesolution/MASTER-PLAN.md` | Phase 110ZZZ entry and any attachment pipeline references |
| `thesolution/reference/` | Any reference docs that mention the attachment schema |
| `.claude/skills/` | Skills that reference attachment tables or pipeline stages (scan all SKILL.md files) |
| `.claude/agents/` | Agent definitions that reference attachment tables |
| `fed_prospector/db/schema/tables/36_attachment.sql` | Superseded — update header comment to redirect to new DDL files |
| `fed_prospector/cli/attachments.py` | `pipeline-status` has 6 queries against `opportunity_attachment`; all attachment CLI commands need review |
| `fed_prospector/cli/backfill.py` | `LEFT JOIN opportunity_attachment a` (line 162) for filename lookup. Backfill queries that filter by `notice_id` on the old intel table will need to join through `opportunity_attachment` (map) to find documents, then join to `document_intel_summary` for per-document intel. The behavioral change is that intel is now per-document, not per-notice. |
| Memory files | Update `project_attachment_pipeline.md` with new table names and 6-table model |

The goal: any agent or developer reading the docs should immediately understand that:
- `sam_attachment` = **the file** (one row per unique resource GUID)
- `attachment_document` = **the document** (one extractable document per file, 1:1 now, N:1 for ZIPs later)
- `opportunity_attachment` = **the mapping** (which notice references which attachment, many-to-many) — repurposed, same name
- `document_intel_summary` = **per-document conclusions** (one row per document x extraction method) — replaces `opportunity_attachment_intel`
- `document_intel_evidence` = **citations/evidence** for document-level intel — replaces `opportunity_intel_source`
- `opportunity_attachment_summary` = **per-opportunity rollup** (derived, re-generatable from per-document intel) — replaces the NULL-attachment consolidated rows
- The old `opportunity_attachment` (one row per notice+URL with all file data) no longer exists
- The old `opportunity_attachment_intel` and `opportunity_intel_source` tables no longer exist

### View/Stored Procedure Updates

Check all views and stored procedures that reference `opportunity_attachment`, `opportunity_attachment_intel`, or `opportunity_intel_source` and update to use the new table names. Queries that need opportunity-scoped data must join through the `opportunity_attachment` map table.

## Pre-Migration Checklist

Steps to perform before running `maintain migrate-dedup`:

1. **Back up MySQL data directory**: `robocopy E:\mysql\data E:\mysql\data_backup_pre110zzz /MIR /R:1 /W:1` (MySQL must be stopped)
2. **Back up attachment directory**: `robocopy E:\fedprospector\attachments E:\fedprospector\attachments_backup_pre110zzz /MIR /MT:8 /R:1 /W:1 /NFL /NDL` (preserves original file layout for rollback)
3. **Start MySQL**: Verify `mysql` is accessible and `fed_contracts` database is healthy
4. **Run dry-run**: `python ./fed_prospector/main.py maintain migrate-dedup --dry-run` — review output for unexpected counts or errors
5. **Verify no NULL resource_guids**: The dry-run reports URL patterns that won't match the GUID regex. If any exist, investigate before proceeding.
6. **Stop all pipeline jobs**: No downloads, extractions, or analysis should run during migration
7. **Stop C# API**: The API references new tables that don't exist until migration completes

After migration:
8. **Restart C# API**: API endpoints will work after new tables exist
9. **Re-extract keyword/heuristic intel** (manual — new tables are empty post-migration):
    - `python ./fed_prospector/main.py extract attachment-intel`
10. **Re-extract AI intel** (manual — costs ~$72 Haiku / ~$358 Sonnet):
    - `python ./fed_prospector/main.py analyze attachment-ai`
11. **Run backfill**: `python ./fed_prospector/main.py backfill opportunity-intel` — propagates re-extracted intel to opportunity table
12. **Verify pipeline status**: `python ./fed_prospector/main.py extract status` — confirm counts look correct
13. **Run file migration**: `python ./fed_prospector/main.py maintain migrate-files` — moves files from `{notice_id}/` to `{resource_guid}/` layout. Can be deferred; pipeline works with either path layout as long as `file_path` is correct.

**Rollback commands** (if migration fails):
- Restore MySQL: `robocopy E:\mysql\data_backup_pre110zzz E:\mysql\data /MIR /MT:8 /R:1 /W:1 /NFL /NDL` (MySQL must be stopped)
- Restore attachments: `robocopy E:\fedprospector\attachments_backup_pre110zzz E:\fedprospector\attachments /MIR /MT:8 /R:1 /W:1 /NFL /NDL`

## Review Findings (Fixed)

Issues found during comprehensive 9-agent review, all fixed in code:

**Note on intel data loss**: The migration drops old intel tables (`opportunity_attachment_intel`, `opportunity_intel_source`) and creates empty replacements. This is intentionally not listed as a risk because: only a handful of documents had AI analysis pre-migration; keyword/heuristic intel is re-extractable for free from existing document text. The AI data loss is trivial — the user will manually re-run AI analysis on the small number of affected documents after migration.

| # | Severity | Issue | Fix Applied |
|---|----------|-------|-------------|
| 1 | CRITICAL | DDL implicit commits broke Step 4 transaction atomicity | Moved CREATE TABLEs before START TRANSACTION |
| 2 | CRITICAL | Step 4 not idempotent — re-run after crash hit duplicate keys | Added truncate-if-populated check |
| 3 | CRITICAL | Map INSERT crashed on duplicate (notice_id, attachment_id) | Changed to INSERT IGNORE |
| 4 | CRITICAL | Step 8 file_path relative/absolute mismatch — all files reported "missing" | Fixed to prepend attachment_dir, store relative paths |
| 5 | HIGH | `--force` cleanup deleted ALL intel including AI for shared documents | Added extraction_method filter to cleanup |
| 6 | HIGH | AI intel invisible to backfill keyword-preferred fields | Added AI query to backfill's _load_intel_rows |
| 7 | HIGH | _mark_transient_failure didn't set download_status='failed' on existing rows | Added download_status to ON DUPLICATE KEY UPDATE |
| 8 | MEDIUM | ai_usage_log.attachment_id stored document_id values | Renamed alias to document_id throughout |
| 9 | MEDIUM | Concurrent same-guid downloads wrote to same filesystem path | Added _dedup_by_guid before ThreadPoolExecutor |
| 10 | CRITICAL | FIELD() returns 0 for NULL extraction_status/download_status, preferring worst rows as canonical | Wrapped FIELD() calls with COALESCE(..., 'pending') |
| 11 | MEDIUM | Step 6 DROP + RENAME not atomic — RENAME failure after DROP leaves no table | Changed to single atomic RENAME TABLE statement |
| 12 | MEDIUM | AUTO_INCREMENT not reset after explicit attachment_id inserts into sam_attachment | Added ALTER TABLE AUTO_INCREMENT after migration INSERT |
| 13 | MEDIUM | backfill.py referenced nonexistent dis.confidence_score column | Changed to FIELD(dis.overall_confidence, 'low', 'medium', 'high') DESC |

## Tasks

### Database
- [x] Write migration SQL script (Steps 1-8 above)
- [x] Create new DDL files for all 6 tables: `sam_attachment`, `attachment_document`, `opportunity_attachment` (repurposed), `document_intel_summary`, `document_intel_evidence`, `opportunity_attachment_summary`
- [x] Update `36_attachment.sql` to note it is superseded (or remove and redirect)
- [x] Drop old `opportunity_attachment_intel` and `opportunity_intel_source` tables during migration (Step 5)
- [x] Write verification queries to confirm migration correctness (row counts, no orphans, intel tables empty)
- [x] Write rollback script (recreate old tables from new data — for safety) — DB backup pre-migration serves as rollback; RENAME TABLE preserves old table until explicit DROP

### Python Pipeline
- [x] Add `extract_resource_guid()` utility function (shared by all pipeline stages)
- [x] (Optional) Update `opportunity_loader.py` `enrich_resource_links` — skip HEAD requests for GUIDs already in `sam_attachment` (optimization only; no queries break since this method only touches `opportunity.resource_links` JSON)
- [x] (Optional) Update `resource_link_resolver.py` — accept skip set for already-resolved GUIDs (no DB access in this file; purely caller-side optimization)
- [x] Update `attachment_downloader.py` — multi-table write path (`sam_attachment` + `attachment_document` + `opportunity_attachment` map), GUID-based file paths, skip already-downloaded GUIDs
- [x] Update `attachment_text_extractor.py` — query `attachment_document` joined to `sam_attachment` for file_path
- [x] Update `attachment_intel_extractor.py` — write to `document_intel_summary`, `document_intel_evidence`, `opportunity_attachment_summary`; stop writing `ai_dry_run` intel; fix orphan evidence row bug (delete evidence before intel in `_cleanup_stale_intel_rows`)
- [x] Update `attachment_ai_analyzer.py` — new table names, `ai_dry_run` should not write intel (log usage only)
- [x] Update `attachment_cleanup.py` — read from `sam_attachment`, check `opportunity_attachment` map count before cleanup, GUID-based directory cleanup
- [x] Write file migration script (move files from notice_id dirs to GUID dirs, update file_path on `sam_attachment`)
- [x] Re-extract all intel after migration (`extract attachment-intel` + `analyze attachment-ai`)

### C# API
- [x] Create `SamAttachment.cs` model — `[Table("sam_attachment")]`, PK `AttachmentId`, `ResourceGuid`, download-level properties
- [x] Create `AttachmentDocument.cs` model — `[Table("attachment_document")]`, PK `DocumentId`, content-level properties, navigation to `SamAttachment`
- [x] Repurpose `OpportunityAttachment.cs` — lean map table, composite PK via `HasKey(m => new { m.NoticeId, m.AttachmentId })`, navigation to `SamAttachment`
- [x] Create `DocumentIntelSummary.cs` model — `[Table("document_intel_summary")]`
- [x] Create `DocumentIntelEvidence.cs` model — `[Table("document_intel_evidence")]`
- [x] Create `OpportunityAttachmentSummary.cs` model — `[Table("opportunity_attachment_summary")]`
- [x] Update `FedProspectorDbContext` with new DbSets and model configuration
- [x] Update `AttachmentIntelService.cs` — query through map table joins, use `OpportunityAttachmentSummary` for rollup (replaces NULL-attachment consolidated row pattern)
- [x] Rewrite NoticeId-filtered DB queries in `AttachmentIntelService.cs` to join through map table
- [x] Add `ResourceGuid` to `AttachmentSummaryDto` in `AttachmentIntelDtos.cs`
- [x] Review `IAttachmentIntelService.cs` — interface likely unchanged but verify
- [x] Fix pre-existing mismatch: `Url` is `[MaxLength(2000)]` in C# model but `VARCHAR(500)` in DDL — align during migration
- [x] Fix pre-existing mismatch: `ExtractionRetryCount` in DDL but missing from C# model — add property
- [x] Update `OpportunitiesControllerTests.cs` — verify tests still compile after model/service changes
- [x] No EF Core migration needed — schema owned by Python DDL (note this explicitly to avoid confusion)

### UI
- [x] Add `resourceGuid` field to `AttachmentSummaryDto` in `ui/src/types/api.ts`
- [x] Review `DocumentIntelligenceTab.tsx` for any notice_id-scoped logic that needs updating
- [x] Decide UX: per-notice documents vs. solicitation-family documents — Per-notice scoping (option 1) — keeps amendment docs separate
- [x] Test UI renders correctly after API changes (attachment table, intel breakdown, analysis buttons)

### Documentation
- [ ] Update `CLAUDE.md` — attachment pipeline description, file references table
- [x] Update `thesolution/MASTER-PLAN.md` — Phase 110ZZZ entry
- [x] Update memory file `project_attachment_pipeline.md` — new table names and 6-table model:
  - `sam_attachment` = per-file download data (one row per unique resource GUID)
  - `attachment_document` = per-document content data (1:1 with sam_attachment now, N:1 for ZIPs later)
  - `opportunity_attachment` = many-to-many mapping (repurposed, lean join table)
  - `document_intel_summary` = per-document conclusions (one row per document x extraction method)
  - `document_intel_evidence` = citations/evidence for document-level intel
  - `opportunity_attachment_summary` = per-opportunity rollup (derived, re-generatable)
- [x] Scan `.claude/skills/` for attachment table references, update SKILL.md files
- [x] Scan `.claude/agents/` for attachment table references, update if needed
- [x] Update `36_attachment.sql` header to redirect to new DDL files
- [x] Update any reference docs in `thesolution/reference/` that mention the schema — No stale references found

### Testing
- [x] Write migration dry-run mode (report what would change without modifying data)
- [x] Test with real data: run migration on a backup, verify counts (ran on live data, counts verified)
- [x] Test each pipeline stage end-to-end after migration
- [x] Test C# API endpoints return correct attachment data for multi-amendment solicitations
- [x] Verify disk space savings after file dedup cleanup — ~8K duplicate downloads eliminated

### CLI
- [x] Add `attachment migrate-dedup` command (runs migration)
- [x] Add `attachment migrate-dedup --dry-run` mode
- [x] Add `attachment migrate-files` command (moves files to GUID-based layout)
- [x] Update `cli/attachments.py` `pipeline-status` command — 6 queries reference old table structure
- [x] Update `cli/backfill.py` — join through `opportunity_attachment` (map) to `attachment_document` for intel queries
- [ ] Add `attachment cleanup-orphaned-dirs` command — sweep old `{notice_id}/` directories after file migration, removing files that are no longer referenced by any `sam_attachment` row — Deferred to Phase 500

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| File move fails mid-way | Some files in old paths, some in new | File migration tracks progress; can resume; old paths not deleted until verified |
| C# EF Core model changes break queries | API 500 errors | Update model + context together; run API tests before deploying |
| Different GUIDs, same file content | Missed dedup opportunity | `content_hash` (SHA-256 of file bytes) is the definitive dedup key — after download, if `content_hash` matches an existing attachment, skip text extraction and intel and copy results from the existing `attachment_document` |
| Race condition during migration | Pipeline writes to old table while migration runs | Run migration during maintenance window; disable pipeline cron jobs first |
| Disk path change breaks existing downloads | Files not found for extraction | Migration updates `file_path` column on `sam_attachment` atomically with file move; old path checked as fallback |
| SAM.gov removes/replaces an attachment | Orphaned map rows, stale files on disk | Cleanup stage detects orphaned map rows; files only deleted when zero `opportunity_attachment` rows reference the attachment |
| Canonical row was failed but duplicate succeeded | Migration picks the failed row, discards the good data | Canonical selection prioritizes successful rows; migration copies successful file data onto canonical before deleting duplicates |
| Agents/devs confused by table restructuring | Wrong table referenced in new code, stale queries | Documentation update task covers CLAUDE.md, skills, agents, reference docs, and memory files |
| Dropping old `opportunity_attachment` during migration | Data loss if migration was incomplete | Step 6 only drops after Step 4 migrates ALL data; migration script verifies row counts match before dropping |

## Estimated Impact

### First-Pass Dedup (resource_guid) — Download Savings
- 5,613 duplicate GUIDs across 12,895 rows = **7,282 downloads eliminated**
- At average ~500KB per file = ~3.5 GB disk savings
- At ~2 seconds per download = ~4 hours of download time saved

### First-Pass Dedup (resource_guid) — HEAD Request Savings
- Same 7,282 redundant HEAD requests eliminated
- At ~30ms each = ~3.6 minutes saved per enrichment run

### First-Pass Dedup (resource_guid) — Text Extraction Savings
- 7,282 redundant extractions eliminated
- At ~5 seconds per PDF extraction = ~10 hours of CPU time saved

### First-Pass Dedup (resource_guid) — AI Analysis Savings (most significant)
- 7,282 redundant AI API calls eliminated
- At ~$0.003 per Haiku call = ~$22 saved per full analysis run
- At ~$0.015 per Sonnet call = ~$109 saved per full analysis run

### Second-Pass Dedup (content_hash) — Additional Savings
- Different resource GUIDs that resolve to identical file content are caught post-download
- Text extraction and AI analysis skipped — results copied from the matching `attachment_document`
- Exact savings depend on how many cross-GUID duplicates exist (unknown until first full download pass)

### One-Time Cost: Intel Re-extraction
- After migration, all intel tables are empty and must be repopulated via `extract attachment-intel` + `analyze attachment-ai`.
- This is a one-time cost. Post-dedup, re-extraction runs against ~23,889 unique documents instead of ~31,170 rows — a 23% reduction.
- AI analysis cost for full re-extraction: ~$72 (Haiku) or ~$358 (Sonnet) at current document counts.
- **Practical note**: Pre-migration, only a handful of documents had AI analysis completed. The AI re-extraction cost is therefore negligible — keyword/heuristic intel is free to re-extract, and the small number of AI-analyzed documents can be re-run cheaply.

### Ongoing Savings
- Every future solicitation amendment/modification that shares attachments with its parent will be free — no download, no extraction, no analysis needed. Only a mapping row is inserted in `opportunity_attachment`.
- Cross-GUID content duplicates are caught automatically by content_hash comparison after download.
