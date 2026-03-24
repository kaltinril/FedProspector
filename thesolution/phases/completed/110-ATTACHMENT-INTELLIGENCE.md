# Phase 110: Opportunity Attachment Intelligence — Download, Extract & Analyze

**Status:** PLANNED
**Priority:** High — attachments contain the competitive intelligence (clearance requirements, evaluation criteria, incumbent info, contract vehicles) that differentiates FedProspect from a SAM.gov mirror
**Dependencies:** None (builds on existing `resource_links` enrichment from Phase 3)

---

## Goal

Download opportunity attachments from SAM.gov, extract text content, and mine structured intelligence that cannot be obtained from the opportunity metadata alone. This transforms FedProspect from a search tool into a decision-support system by surfacing bid/no-bid signals buried inside solicitation documents.

## Problem

SAM.gov opportunity metadata tells you *what* is being solicited but not *how* to win it. The critical details — security clearance requirements, evaluation criteria (LPTA vs Best Value), contract vehicle type, incumbent identity, and scope of work — are locked inside PDF/Word attachments. Today FedProspect stores attachment URLs and filenames (`resource_links` JSON) but never downloads or reads the actual documents.

Without this capability, FedProspect is functionally a SAM.gov search wrapper with no unique value proposition.

## Competitive Context

SAM.gov itself provides **zero** structured extraction from attachments — it's purely raw document hosting. This gap is exactly what premium tools charge $7,500–$42,000/year to fill.

| Competitor | Document Intel Approach | Annual Cost |
|-----------|------------------------|-------------|
| **Deltek GovWin IQ** | Analyst-curated + AI Smart Summaries, proposal outlines | $12,000–$42,000 |
| **Bloomberg Government (BGOV)** | ML/NLP keyword search *inside* attachments — claims to be "the only solution" doing this | $7,500–$14,000 |
| **GovDash** | Azure Document Intelligence OCR → LLM extraction → compliance matrices | Est. $6,000+ |
| **CLEATUS** | AI Document Hub, automated solicitation analysis | $3,600 |
| **Sweetspot** (YC-backed) | Extracts "the relevant 20%" from solicitation docs | Custom |
| **GovTribe** | Basic — titles/descriptions only, no attachment content | $1,350–$5,500 |
| **FedProspect Phase 110** | Hybrid keyword + Claude Haiku/Sonnet Batch API | **~$84/year in AI costs** |

BGOV's keyword-search-inside-attachments is considered a premium differentiator worth $7,500+/year. Building this into FedProspect for ~$7/month is a **170x cost advantage**. GovDash (the AI-native leader) does full LLM extraction from PDFs — our hybrid tiered approach achieves similar results at a fraction of the cost by using free keyword extraction first and reserving AI for ambiguous documents.

**What competitors do that we don't need to build:**
- Proposal generation/writing (GovDash, CLEATUS, GovSignals)
- Compliance matrix generation (GovDash, Federal Compass)
- Multi-source aggregation across state/local (Sweetspot, CLEATUS)

**Legal:** Federal solicitation documents are public domain under 17 USC §105. SAM.gov's TOS prohibits web scraping but explicitly provides an API for programmatic access — using it within rate limits is the sanctioned path. Extracted intelligence (clearance requirements, eval criteria, etc.) is derived analysis with no copyright or TOS concerns.

## What We Already Have

| Asset | Location | Status |
|-------|----------|--------|
| Attachment URLs | `opportunity.resource_links` (JSON column) | Captured during opportunity load |
| Metadata enrichment | `resource_link_resolver.py` — HEAD requests for filename + content-type | Working, CLI: `python main.py update link-metadata` |
| Reserved DB columns | `security_clearance_required`, `incumbent_uei`, `incumbent_name`, `contract_vehicle_type` on `opportunity` table | Created but unpopulated |
| Description text | `opportunity.description_text` (LONGTEXT) | Cached from SAM.gov description API |

---

## Intelligence Targets

These are the structured fields we want to extract from attachments:

| Field | Why It Matters | Example |
|-------|---------------|---------|
| **Scope of Work Summary** | Quick bid/no-bid decision without reading 50-page SOW | "IT helpdesk support for 3 embassy locations in West Africa" |
| **Security Clearance** | Immediate disqualifier if org/personnel lack clearance | "Active Secret clearance required for all key personnel" |
| **Clearance Scope** | Who needs it — the company (FCL) or individual employees (PCL)? | Facility Clearance Level: Secret; Personnel: TS/SCI for PM |
| **Evaluation Method** | LPTA = price wins; Best Value = past performance matters | LPTA per FAR 15.101-2 |
| **Contract Vehicle** | Determines if org is eligible to bid | OASIS SB Pool 1, GSA MAS SIN 541611 |
| **New vs Recompete** | Recompetes favor incumbents; new work is open field | "Follow-on to Contract GS-10F-0XXX, incumbent: Booz Allen" |
| **Incumbent Identity** | Know who you're competing against | Current contractor: SAIC, contract expires 09/2026 |
| **Period of Performance** | Contract duration affects pricing and staffing | Base year + 4 option years |
| **Labor Categories** | Match against org's available talent | "Program Manager (PMP required), Sr. Systems Engineer (TS/SCI)" |
| **Key Requirements** | Domain-specific qualifications, certifications, standards | CMMI Level 3, ISO 27001, FedRAMP authorization |

---

## Implementation Options Analysis

### Option A: Regex/Keyword Extraction (Free, Fast, All Documents)

Extract text from documents, then run pattern matching to identify intelligence targets.

**How it works:**
1. Download attachment (PDF/Word/Excel) to temp storage
2. Extract text via PyMuPDF (PDF), python-docx (Word), openpyxl (Excel)
3. If PDF text extraction yields < 50 chars/page → scanned document → OCR via Tesseract/OCRmyPDF
4. Run regex patterns against extracted text, capture matches + surrounding context (200 chars)
5. Store results in DB with confidence indicators

**Keyword patterns by category:**

*Security Clearance:*
- `TS/SCI`, `Top Secret`, `Secret` (not "Secret Service"), `Confidential clearance`
- `facility clearance`, `FCL`, `personnel clearance`, `PCL`
- `public trust`, `moderate risk`, `high risk`
- `SF-86`, `e-QIP`, `SF-312`, `DCSA`, `SCIF`
- `NAC`, `NACI`, `NACLC`, `SSBI`, `T1`–`T5` (investigation types — use context-aware patterns to avoid false positives like "Section T5")

*Evaluation Method:*
- `lowest price technically acceptable`, `LPTA`
- `best value`, `trade-off`, `tradeoff`, `lowest price` (standalone, without "technically acceptable")
- `FAR 15.101-1` (tradeoff), `FAR 15.101-2` (LPTA)
- `evaluation factor`, `evaluation criteria`

*Contract Vehicle:*
- `OASIS`, `OASIS+`, `OASIS SB`
- `GSA Schedule`, `GSA MAS`, `GSA/MAS`, `Federal Supply Schedule`, `FSS`
- `BPA`, `Blanket Purchase Agreement`
- `IDIQ`, `Indefinite Delivery`, `Indefinite Quantity`
- `GWAC`, `SEWP`, `CIO-SP3`, `CIO-SP4`, `Alliant`, `VETS 2`, `8(a) STARS`
- `SIN` + number pattern (GSA Schedule SIN numbers)

*New vs Recompete:*
- `incumbent`, `current contractor`, `currently performed by`
- `follow-on`, `recompete`, `re-compete`
- `new requirement`, `new start`
- `bridge contract`, `bridge extension`, `successor contract`
- `previous contract number`, `transition plan`, `transition period`

*Document Type (by filename):*
- SOW, PWS, SOO (scope documents)
- RFP, RFQ, RFI (solicitation type)
- SF1449, SF33, SF30 (standard forms)
- Section L/M (instructions/evaluation)
- QASP (quality assurance)
- CLIN (contract line items)

**Strengths:** Zero cost, fast, deterministic, works on all documents
**Weaknesses:** Can't summarize scope, misses paraphrased requirements, no semantic understanding
**Coverage:** ~60-70% of intelligence targets (clearance, eval method, vehicle, recompete indicators)

### Option B: AI Document Analysis via Claude Batch API (Cheap, High Quality)

Send extracted document text to Claude API for structured extraction.

**How it works:**
1. Same text extraction as Option A (PyMuPDF, etc.)
2. Send text + structured extraction prompt to Claude Haiku via Batch API
3. Receive JSON response with all intelligence fields populated
4. Store results in DB

**Cost estimates (Haiku 4.5 via Batch API — 50% discount):**

| Volume | Input cost | Output cost | Total |
|--------|-----------|-------------|-------|
| 100 docs/month | $0.20 | $0.25 | **$0.45** |
| 1,000 docs/month | $2.00 | $2.50 | **$4.50** |
| 5,000 docs/month | $10.00 | $12.50 | **$22.50** |

*Assumptions: avg 10 pages/doc ≈ 8,000-12,000 input tokens (government docs are dense); ~500 output tokens. Costs above use 4K tokens — actual costs may be 2-3x higher before prompt caching. Prompt caching reduces input cost further by up to 90%. See [Anthropic pricing](https://docs.anthropic.com/en/docs/about-claude/pricing) for current rates.*

**With prompt caching (same system prompt across batch):**

| Volume | Estimated total with caching |
|--------|------------------------------|
| 1,000 docs/month | **~$3.00** |
| 5,000 docs/month | **~$15.00** |

**Strengths:** Handles all intelligence targets including scope summaries, understands context and nuance, high accuracy
**Weaknesses:** Requires API key + spend, non-real-time (batch = up to 24hr turnaround), rate limits apply
**Coverage:** ~95%+ of intelligence targets

### Option C: Hybrid Tiered Approach (Recommended)

Combine Options A and B in tiers of increasing cost:

```
Tier 1 — Regex/Keyword (FREE, ALL documents)
  Run pattern matching on every downloaded document
  Store: detected clearance level, eval method, vehicle type, recompete indicators
  Assign confidence: HIGH (multiple strong matches), MEDIUM (some matches), LOW (no/weak matches)
      │
      ▼
Tier 2 — Heuristic Classification (FREE, ALL documents)
  Section header detection: "SECTION M - EVALUATION", "SECURITY REQUIREMENTS"
  FAR/DFARS clause extraction: FAR 52.204-2 = security, FAR 15.101 = eval method
  Document type classification by filename
      │
      ▼
Tier 3 — Claude Haiku Batch API (CHEAP, AMBIGUOUS documents only)
  Send documents where Tier 1+2 confidence = LOW or MEDIUM
  Also send ALL documents for high-priority/prospected opportunities
  Cost: ~$0.003/document (~$3-15/month for typical volume)
      │
      ▼
Tier 4 — Claude Sonnet Deep Analysis (MODERATE, HIGH-VALUE only)
  On-demand when user clicks "Deep Analysis" on a prospected opportunity
  Full scope summary, compliance gap analysis, competitive positioning
  Cost: ~$0.01/document
```

**Estimated monthly cost for 5,000 opportunities:**
- Tier 1-2: $0
- Tier 3 (30% need AI): ~$4.50
- Tier 4 (5% deep analysis): ~$2.50
- **Total: ~$7/month**

---

## Recommended Approach: Option C (Hybrid Tiered)

Option C gives us full coverage at minimal cost by reserving expensive AI analysis for documents where cheap extraction falls short or where the opportunity is high-value enough to justify it.

### Implementation Rounds

#### Round 1: Download & Extract Text (Foundation)

Build the infrastructure to download attachments, extract text, and store it.

**Task 1: Attachment storage schema**

New table: `opportunity_attachment`

```sql
CREATE TABLE opportunity_attachment (
    attachment_id      INT AUTO_INCREMENT PRIMARY KEY,
    notice_id          VARCHAR(100) NOT NULL,
    url                VARCHAR(500) NOT NULL,       -- SAM.gov resource URLs are ~104 chars; 500 avoids prefix index issues
    filename           VARCHAR(500),
    content_type       VARCHAR(100),
    file_size_bytes    BIGINT,
    file_path          VARCHAR(500),        -- local storage path
    extracted_text     LONGTEXT,            -- annotated markdown (preserves headings, bold, tables), not flat plain text
    page_count         INT,
    is_scanned         TINYINT DEFAULT 0,   -- 1 if OCR was needed
    ocr_quality        ENUM('good','fair','poor'),
    download_status    ENUM('pending','downloaded','failed','skipped') DEFAULT 'pending',
    extraction_status  ENUM('pending','extracted','failed','unsupported') DEFAULT 'pending',
    content_hash       CHAR(64),            -- SHA-256 of raw file bytes; skip reprocessing if unchanged
    text_hash          CHAR(64),            -- SHA-256 of extracted text; detect if re-extraction produces different output
    downloaded_at      DATETIME,
    extracted_at       DATETIME,
    last_load_id       INT,                 -- ETL load that last touched this row
    created_at         DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_notice (notice_id),
    INDEX idx_status (download_status, extraction_status),
    UNIQUE INDEX idx_url (notice_id, url)    -- prevent duplicate rows for same attachment
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

**Task 2: Attachment downloader**

New module: `fed_prospector/etl/attachment_downloader.py`
- Download files from `resource_links` URLs to local storage (`data/attachments/{notice_id}/`)
- Follow SAM.gov 303 redirects to S3
- **SSRF protection**: reuse `_ALLOWED_PREFIXES` from `resource_link_resolver.py` on initial URL; validate redirect target is `*.amazonaws.com` (S3); limit to 1 redirect hop; validate Content-Type before writing (reject `text/html` etc.)
- Store file metadata in `opportunity_attachment` table
- Compute SHA-256 `content_hash` of downloaded bytes for change detection
- Respect rate limiting (configurable delay between downloads)
- Skip files already downloaded (idempotent via `--missing-only`)
- Support file size limits (skip attachments > configurable max, e.g., 50MB)
- Stream downloads to disk (`iter_content`) to avoid loading large files into memory
- CLI: `python main.py download attachments [--notice-id=X] [--batch-size=100] [--max-file-size=50] [--check-changed]`

**Task 3: Text extraction engine (structure-aware)**

New module: `fed_prospector/etl/attachment_text_extractor.py`

**Why structure-aware extraction matters:** Government solicitations are structurally rich — headings mark sections ("SECTION M - EVALUATION CRITERIA", "SECURITY REQUIREMENTS"), bold text marks key terms ("Active Secret Clearance required"), tables contain evaluation factor weights and labor category matrices, and numbered lists enumerate evaluation factors in ranked order. Preserving this structure in the extracted text makes free Tier 1/2 keyword extraction significantly more accurate with fewer false positives, narrowing the gap with paid AI extraction. A "Secret" match under a "SECURITY REQUIREMENTS" heading is high confidence; the same match in a cover letter is noise.

Output format: **annotated markdown** stored in `opportunity_attachment.extracted_text`. This is human-readable, regex-friendly, and preserves the structural signals that downstream extraction relies on.

Extract text from downloaded files based on content type:

- **PDF → PyMuPDF (fitz)** primary, with structure-aware extraction:
  - Use `span["size"]` and `span["flags"]` (bold=16, italic=2) per text span to detect formatting
  - Infer heading hierarchy from font size jumps (e.g., 14pt+ → `##` markdown heading)
  - Preserve bold spans → `**bold**` markdown markers
  - Extract tables via PyMuPDF table extraction → markdown tables
  - Maintain reading order (multi-column detection where possible)
  - Detect scanned pages (< 50 chars/page) → fall back to OCR
- **Scanned PDF → OCRmyPDF + Tesseract** — plain text fallback (no structural signals available from OCR output)
- **Word (.docx) → python-docx** with formatting inspection (not just `paragraph.text`):
  - Preserve heading hierarchy via `paragraph.style.name` → markdown `#`/`##`/`###`
  - Detect "fake headings" (Normal style but bold + larger font size) via run font properties → treat as headings
  - Detect bold runs → wrap in `**bold**` markers
  - Extract tables via `document.tables` API → markdown tables (eval criteria, CLIN structures, labor cats)
  - Detect list items via style names (`List Bullet`, `List Number`) → markdown `- ` / `1. `
  - Iterate `document.element.body` children to maintain correct document order (paragraphs interleaved with tables)
  - Access `paragraph._element` for edge cases (list numbering from `numPr`, text boxes from `w:txbxContent`)
- **Excel (.xlsx) → openpyxl** with structure preservation:
  - Output sheet names as markdown headings
  - Detect merged cells and header rows (often bold/colored) → markdown table headers
  - Preserve cell formatting signals (bold headers, colored emphasis cells)
  - Extract cell values as markdown tables
- **Plain text → direct read**

- Store extracted annotated markdown in `opportunity_attachment.extracted_text`
- Track extraction status and quality metrics
- CLI: `python main.py extract attachment-text [--notice-id=X] [--batch-size=100]`

#### Round 2: Keyword Intelligence Extraction (Free Tier)

**Task 4: Regex intelligence extractor**

New module: `fed_prospector/etl/attachment_intel_extractor.py`
- Run keyword/regex patterns against extracted annotated markdown from attachments
- **Also run against `opportunity.description_text`** (already cached in DB, free — set `attachment_id = NULL` in intel/source tables)
- Extract structured intelligence for each category (clearance, eval method, vehicle, recompete)
- Capture match context (surrounding text) for human review and provenance
- Write one `opportunity_intel_source` row per match per field (provenance trail)
- Assign confidence scores based on match count and pattern strength

**Structure-aware matching** — leverage the annotated markdown from Task 3:
- **Section-aware matching**: keywords found under relevant headings get confidence boost (e.g., "Secret" under a `## SECURITY REQUIREMENTS` heading = high confidence clearance requirement; "Secret" in body text near "Secretary" = needs more context)
- **Bold-aware matching**: keywords found in `**bold**` markers get confidence boost (government docs often bold key requirements)
- **Table-aware matching**: evaluation criteria found in markdown table rows can extract factor weights alongside factor names; CLIN tables can extract labor categories with associated requirements
- UPSERT intel rows using `(notice_id, attachment_id, extraction_method)` unique index

New table: `opportunity_attachment_intel`

```sql
CREATE TABLE opportunity_attachment_intel (
    intel_id              INT AUTO_INCREMENT PRIMARY KEY,
    notice_id             VARCHAR(100) NOT NULL,
    attachment_id         INT,                           -- NULL if from description_text
    extraction_method     ENUM('keyword','heuristic','ai_haiku','ai_sonnet') NOT NULL,
    source_text_hash      CHAR(64),                     -- SHA-256 of the text that was analyzed; if attachment text changes, we know to re-extract

    -- Security clearance
    clearance_required    CHAR(1),                       -- 'Y'=yes, 'N'=no, NULL=unknown (matches opportunity.security_clearance_required)
    clearance_level       VARCHAR(50),                   -- 'Secret', 'Top Secret', 'TS/SCI', 'Public Trust'
    clearance_scope       VARCHAR(50),                   -- 'facility', 'personnel', 'both'
    clearance_details     TEXT,                           -- raw matched context

    -- Evaluation method
    eval_method           VARCHAR(50),                   -- 'LPTA', 'Best Value', 'Trade-Off'
    eval_details          TEXT,

    -- Contract vehicle
    vehicle_type          VARCHAR(100),                  -- 'OASIS SB', 'GSA MAS', 'IDIQ', 'BPA', etc.
    vehicle_details       TEXT,

    -- New vs recompete
    is_recompete          CHAR(1),                       -- 'Y'=yes, 'N'=no, NULL=unknown
    incumbent_name        VARCHAR(200),
    recompete_details     TEXT,

    -- Scope summary
    scope_summary         TEXT,                          -- AI-generated or section extract
    period_of_performance VARCHAR(200),
    labor_categories      JSON,                          -- ["PM", "Sr Engineer", ...]
    key_requirements      JSON,                          -- ["CMMI L3", "FedRAMP", ...]

    -- Confidence
    overall_confidence    ENUM('high','medium','low') NOT NULL,
    confidence_details    JSON,                          -- per-field confidence breakdown

    -- Tracking
    last_load_id          INT,                           -- ETL load that last touched this row
    extracted_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_notice (notice_id),
    INDEX idx_clearance (clearance_required, clearance_level),
    INDEX idx_eval (eval_method),
    INDEX idx_vehicle (vehicle_type),
    INDEX idx_recompete (is_recompete),
    UNIQUE INDEX idx_upsert (notice_id, attachment_id, extraction_method)  -- enables UPSERT on re-extraction
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

**Source provenance table** — every extracted fact links back to exactly where it came from:

```sql
CREATE TABLE opportunity_intel_source (
    source_id             INT AUTO_INCREMENT PRIMARY KEY,
    intel_id              INT NOT NULL,                  -- FK to opportunity_attachment_intel
    field_name            VARCHAR(50) NOT NULL,          -- which intel field: 'clearance_level', 'eval_method', etc.
    attachment_id         INT,                           -- which attachment the evidence came from
    source_filename       VARCHAR(500),                  -- human-readable: "SOW_Document.pdf"
    page_number           INT,                           -- page in original document (NULL for Word/text)
    char_offset_start     INT,                           -- position in extracted text where match begins
    char_offset_end       INT,                           -- position where match ends
    matched_text          VARCHAR(500),                  -- the exact text that triggered the match ("Active Secret Security Clearance")
    surrounding_context   TEXT,                          -- ~300 chars around the match for human review
    pattern_name          VARCHAR(100),                  -- which regex pattern matched (e.g., 'clearance_level_secret')
    extraction_method     ENUM('keyword','heuristic','ai_haiku','ai_sonnet') NOT NULL,
    confidence            ENUM('high','medium','low') NOT NULL,
    created_at            DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_intel (intel_id),
    INDEX idx_attachment (attachment_id),
    INDEX idx_field (field_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

- CLI: `python main.py extract attachment-intel [--notice-id=X] [--batch-size=100] [--method=keyword]`

**Task 5: Populate reserved opportunity columns**

After intel extraction, update the reserved columns on the `opportunity` table:
- `security_clearance_required` ← from `clearance_required`
- `incumbent_uei` / `incumbent_name` ← from recompete analysis
- `contract_vehicle_type` ← from vehicle detection

This makes intel available in existing opportunity queries and the UI without joining.

#### Round 3: AI-Powered Analysis (Paid Tier)

**Task 6: Claude Batch API integration**

New module: `fed_prospector/etl/attachment_ai_analyzer.py`
- Build structured extraction prompt (system prompt + document text + JSON schema)
- Submit documents to Claude Haiku 4.5 via Anthropic Batch API
- Process batch results and merge with keyword-extracted intel
- AI results override keyword results when confidence is higher
- Track API usage and costs in `etl_load_log`
- CLI: `python main.py extract attachment-ai [--notice-id=X] [--batch-size=50] [--model=haiku] [--force]`

**Task 7: On-demand deep analysis endpoint**

Uses the existing `DataLoadRequests` queue pattern (same as `AwardsController.RequestLoadAsync`). The API does NOT call Claude directly — it inserts a request row that the Python CLI picks up.

New endpoint on `OpportunitiesController`:
```
POST /api/v1/opportunities/{noticeId}/analyze
```
- `[EnableRateLimiting("write")]` (30/min per user — already configured)
- Inserts row into `data_load_request` table: `{ type: 'attachment_analysis', target_id: noticeId, tier: 'haiku'|'sonnet', status: 'PENDING' }`
- Returns `LoadRequestStatusDto` (existing DTO) with request ID so UI can poll
- Python CLI checks `data_load_request` table, runs analysis, updates status to `COMPLETED`
- No new C# service needed — reuses existing `IDataLoadRequestService` to insert/query request rows

New read endpoint on `OpportunitiesController`:
```
GET /api/v1/opportunities/{noticeId}/document-intelligence
```
- Returns extracted intel + attachments + provenance sources in a single call
- New service: `IAttachmentIntelService` → `AttachmentIntelService`
- Queries `opportunity_attachment_intel` joined with `opportunity_intel_source` and `opportunity_attachment`
- No org isolation needed — opportunity data is public (shared data, not org-scoped)

**New DTOs** in `FedProspector.Core/DTOs/Intelligence/AttachmentIntelDtos.cs`:

```csharp
public class DocumentIntelligenceDto
{
    public string NoticeId { get; set; } = "";
    public int AttachmentCount { get; set; }
    public int AnalyzedCount { get; set; }
    public string? LatestExtractionMethod { get; set; }      // "keyword", "ai_haiku", "ai_sonnet"
    public DateTime? LastExtractedAt { get; set; }

    // Consolidated intel (best available across all attachments)
    public string? ClearanceRequired { get; set; }            // "Y", "N", null
    public string? ClearanceLevel { get; set; }               // "Secret", "Top Secret", "TS/SCI"
    public string? ClearanceScope { get; set; }               // "facility", "personnel", "both"
    public string? EvalMethod { get; set; }                   // "LPTA", "Best Value", "Trade-Off"
    public string? VehicleType { get; set; }                  // "OASIS SB", "GSA MAS", etc.
    public string? IsRecompete { get; set; }                  // "Y", "N", null
    public string? IncumbentName { get; set; }
    public string? ScopeSummary { get; set; }
    public string? PeriodOfPerformance { get; set; }
    public List<string> LaborCategories { get; set; } = new();
    public List<string> KeyRequirements { get; set; } = new();
    public string OverallConfidence { get; set; } = "low";

    // Provenance — one entry per extracted field with source evidence
    public List<IntelSourceDto> Sources { get; set; } = new();

    // Attachment list
    public List<AttachmentSummaryDto> Attachments { get; set; } = new();
}

public class IntelSourceDto
{
    public string FieldName { get; set; } = "";               // "clearance_level", "eval_method", etc.
    public string? SourceFilename { get; set; }
    public int? PageNumber { get; set; }
    public string? MatchedText { get; set; }
    public string? SurroundingContext { get; set; }
    public string ExtractionMethod { get; set; } = "";
    public string Confidence { get; set; } = "";
}

public class AttachmentSummaryDto
{
    public int AttachmentId { get; set; }
    public string Filename { get; set; } = "";
    public string? ContentType { get; set; }
    public long? FileSizeBytes { get; set; }
    public int? PageCount { get; set; }
    public string DownloadStatus { get; set; } = "";
    public string ExtractionStatus { get; set; } = "";
}
```

**New files:**
- `FedProspector.Core/DTOs/Intelligence/AttachmentIntelDtos.cs` — DTOs above
- `FedProspector.Core/Interfaces/IAttachmentIntelService.cs` — interface
- `FedProspector.Infrastructure/Services/AttachmentIntelService.cs` — EF Core queries with `.AsNoTracking()`

**Modified files:**
- `OpportunitiesController.cs` — add 2 endpoints + inject `IAttachmentIntelService`
- `Program.cs` — register `AddScoped<IAttachmentIntelService, AttachmentIntelService>()`
- `FedProspectorDbContext.cs` — add `DbSet` for 3 new tables + entity mappings

#### Round 4: UI Integration

**Task 8: Document Intelligence tab**

New tab on Opportunity Detail page (6th tab, follows existing tab pattern).

**New files:**
- `ui/src/pages/opportunities/DocumentIntelligenceTab.tsx`

**Modified files:**
- `ui/src/api/opportunities.ts` — add `getDocumentIntelligence(noticeId)` and `requestAnalysis(noticeId, tier)`
- `ui/src/types/api.ts` — add `DocumentIntelligenceDto`, `IntelSourceDto`, `AttachmentSummaryDto`
- `ui/src/queries/queryKeys.ts` — add `documentIntelligence: (noticeId) => [...]`
- `ui/src/pages/opportunities/OpportunityDetailPage.tsx` — register new tab

**Tab content:**
- `useQuery` fetches `getDocumentIntelligence(noticeId)` — single API call gets everything
- Intel fields displayed as a summary card grid (clearance, eval method, vehicle, incumbent, scope)
- Each field shows confidence badge (green/yellow/red chip via MUI `Chip`)
- Each field has "View Source" expand — shows `IntelSourceDto` entries (filename, page, matched text in context)
- Attachment list at bottom (filename, type, size, status)
- "Analyze with AI" button uses `useMutation` → `requestAnalysis(noticeId, 'haiku')` → snackbar confirmation → poll or refetch
- If no intel exists yet: empty state with "No document intelligence available. Run `extract attachment-intel` or click Analyze."

---

## Change Detection & Idempotency

Uses SHA-256 hashing like the rest of the ETL pipeline (`etl/change_detector.py`), but adapted for a multi-stage file processing pipeline rather than single-table record comparison. The existing `ChangeDetector` batch-loads all hashes and classifies records as insert/update/unchanged. Here, each processing stage has its own hash column checked independently — this is necessary because download → extraction → intel is a pipeline, not a single-table load.

### How it works

Each processing stage tracks a hash so re-runs skip already-processed documents:

| Stage | Hash Column | What's Hashed | Skip Condition |
|-------|-------------|---------------|----------------|
| Download | `opportunity_attachment.content_hash` | SHA-256 of raw file bytes | File at URL has same hash → skip re-download |
| Text extraction | `opportunity_attachment.text_hash` | SHA-256 of extracted text | Text hash unchanged → skip re-extraction |
| Intel extraction | `opportunity_attachment_intel.source_text_hash` | SHA-256 of the text that was analyzed | Text hash matches existing intel row → skip |

### Idempotency modes

Two distinct operations — don't conflate them:

1. **`--missing-only` (default)** — skip attachments that already have a row in the table. Fast, no re-downloading. This is the normal batch mode.
2. **`--check-changed`** — re-download and compare `content_hash`. If SAM.gov updated the file, re-extract text and intel. Slower (must download to compare), but catches document revisions. Run periodically (weekly?) or on-demand.
3. **`--force`** — re-process everything regardless of hashes. Use when extraction logic changes (new keyword patterns, updated AI prompt).

### Re-processing triggers

Intel is re-extracted only when:
1. **Attachment content changes** — detected via `--check-changed` mode (re-download, compare `content_hash`)
2. **Extraction logic changes** — new keyword patterns added or AI prompt updated → `--force` flag bypasses hash check
3. **Manual request** — user clicks "Re-analyze" in UI

### Deduplication

- `opportunity_attachment` has a unique index on `(notice_id, url)` — same URL for the same opportunity won't create duplicate rows
- `opportunity_attachment_intel` stores one row per `(notice_id, attachment_id, extraction_method)` — re-extraction UPSERTs, doesn't INSERT duplicates
- Download commands use `--missing-only` (default) to skip attachments already in the table

---

## Provenance & Source Tracking

Every extracted fact must trace back to the exact text and location that produced it. Users need this because:

1. **Validation** — keyword/AI extraction can get semantics wrong (e.g., "Secret" in "Secretary of Defense" ≠ clearance requirement)
2. **Trust** — users won't act on extracted intel unless they can verify the source
3. **Audit trail** — bid/no-bid decisions based on extracted intel need documented backing

### How provenance works

The `opportunity_intel_source` table stores one row per evidence match per field:

```
Intel record says: clearance_level = "Secret"
  └─ Source 1: SOW_Document.pdf, page 12, chars 4501-4532
     matched_text: "Active Secret Security Clearance"
     context: "...all key personnel must possess an Active Secret Security Clearance prior to contract start..."
     pattern: clearance_level_secret
     confidence: high

  └─ Source 2: RFP_Instructions.pdf, page 3, chars 892-915
     matched_text: "Secret clearance required"
     context: "...the contractor facility must hold a Secret clearance required by DCSA..."
     pattern: clearance_facility
     confidence: high
```

### UI display

In the Document Intelligence tab, each extracted field shows:
- The extracted value (e.g., "Secret Clearance — Personnel")
- Confidence badge (green/yellow/red)
- **"View Source" link** — expands to show:
  - Source filename + page number
  - The exact matched text, **highlighted in context**
  - Which extraction method produced it (keyword vs AI)
  - Multiple sources listed if the same fact was found in multiple places (strengthens confidence)

This lets users quickly verify: "Yes, page 12 of the SOW really does say Active Secret clearance" or "No, that's a false positive — it's talking about the Secretary, not a security clearance."

### AI provenance

For AI-extracted intel (Haiku/Sonnet), the prompt instructs Claude to include source quotes:

```json
{
  "clearance_level": "Secret",
  "clearance_evidence": "Page 12: 'all key personnel must possess an Active Secret Security Clearance'",
  "clearance_scope": "personnel",
  "clearance_scope_evidence": "Page 12: 'key personnel' indicates individual PCL, not facility FCL"
}
```

The `_evidence` fields are stored as `matched_text` + `surrounding_context` in `opportunity_intel_source`, same as keyword matches. This gives uniform provenance regardless of extraction method.

---

## Process Architecture: When Does Extraction Run?

Three modes, configurable:

### Mode 1: Batch Enrichment (Default)

Scheduled process that runs periodically (daily or on-demand):

```
python main.py download attachments --missing-only --batch-size=200
python main.py extract attachment-text --pending-only --batch-size=200
python main.py extract attachment-intel --pending-only --method=keyword
python main.py extract attachment-ai --low-confidence-only --model=haiku
```

**When:** After opportunity load completes, as a separate enrichment step.
**Pros:** Simple, batch-friendly, predictable costs.
**Cons:** Intelligence not available immediately for new opportunities.

### Mode 2: On-Demand per Opportunity

User clicks "Enrich" or "Analyze" button on an opportunity detail page:

```
POST /api/opportunities/{noticeId}/enrich    → download + extract + keyword
POST /api/opportunities/{noticeId}/analyze   → send to AI for deep analysis
```

**When:** User is evaluating a specific opportunity.
**Pros:** Zero background cost, only processes what users care about.
**Cons:** First view is slow (download + extract takes seconds), AI analysis has latency.

### Mode 3: Auto-Enrich on Prospect

When a user prospects an opportunity (adds it to their pipeline), automatically trigger attachment enrichment:

```
Prospect action → download attachments → extract text → keyword intel → queue for Haiku batch
```

**When:** Opportunity enters the user's pipeline.
**Pros:** Intelligence ready when user needs it, targets spend on relevant opportunities.
**Cons:** Slightly more complex orchestration.

**Recommendation:** Start with **Mode 1** (batch enrichment) for Round 1-2. Add **Mode 2** (on-demand) in Round 3 when AI analysis is available. Consider **Mode 3** as a future enhancement.

---

## Storage & Disk Considerations

**Attachment file storage:**
- Average attachment: ~500KB (PDFs range from 50KB to 10MB+)
- 5,000 opportunities × 3 attachments avg × 500KB = ~7.5 GB
- Store in `data/attachments/{notice_id}/` on local filesystem
- Add configurable max file size (default 50MB) and total storage cap
- Consider cleanup policy: delete files after text extraction, keep only extracted text

**Extracted text storage:**
- Average extracted text: ~50KB per document
- 15,000 documents × 50KB = ~750 MB in MySQL LONGTEXT columns
- Well within MySQL capabilities

**Option: Text-only mode**
- Download → extract text → delete original file
- Reduces storage from ~7.5 GB to ~750 MB
- Lose ability to re-extract or view originals
- Recommended for initial deployment; revisit if users need original file viewing

---

## Python Dependencies

```
pymupdf>=1.25.0        # PDF text extraction (import fitz)
python-docx>=1.1.0     # Word .docx extraction
openpyxl>=3.1.0        # Excel .xlsx extraction
anthropic>=0.40.0      # Claude API (Batch API support) — for Round 3
```

**Optional (for scanned PDF OCR):**
```
ocrmypdf>=16.0         # Wraps Tesseract for scanned PDFs
```
Tesseract must be installed as a system binary:
- Windows: [UB Mannheim builds](https://github.com/UB-Mannheim/tesseract/wiki)
- Linux: `apt install tesseract-ocr`

---

## Gotchas, Limitations & Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| **SAM.gov rate limiting on downloads** | Downloads could be throttled or blocked | Configurable delay between downloads (default 0.5s); batch during off-hours; track HTTP 429 responses |
| **Scanned PDFs** | ~20-30% of gov docs are scanned images, no text to extract | Detect via low char count, fall back to Tesseract OCR; track OCR quality |
| **Encrypted/password-protected PDFs** | Can't extract text | Detect and flag as `extraction_status = 'failed'`; log for manual review |
| **Very large files** | SOWs can be 200+ pages, attachments can be ZIP bundles | Max file size limit; max page count for AI analysis; skip ZIP files initially |
| **AI cost overruns** | Unexpected volume spike could increase Haiku/Sonnet spend | Daily/monthly cost caps in config; alert when approaching limit; default to keyword-only |
| **False positive keyword matches** | "Secret" in "Secretary" or document title | Use word-boundary patterns (`\bSecret\b`); require context (nearby words like "clearance", "level") |
| **Stale attachments** | SAM.gov URLs may expire or change | Re-download on 404; track URL validity; don't assume permanent availability |
| **Disk space** | Thousands of PDFs consume storage | Text-only mode (delete after extraction); configurable retention policy |
| **Tesseract accuracy** | 80-85% on real government docs | Good enough for keyword extraction; flag low-quality OCR for AI fallback |
| **Non-English documents** | Some international opportunities have non-English attachments | Detect language; skip non-English for keyword extraction; AI handles multilingual |
| **Claude API availability** | Batch API may have latency or rate limits | Batch API is async (up to 24hr); design for eventual consistency, not real-time |
| **Malicious PDF content** | PyMuPDF/fitz has had CVEs for crafted PDFs | Keep PyMuPDF updated; consider running extraction in sandboxed subprocess; SAM.gov is trusted but defense-in-depth matters |
| **SSRF via redirect** | SAM.gov 303 redirect target could theoretically be hijacked | Validate redirect target is `*.amazonaws.com`; limit to 1 hop; validate Content-Type before writing |

---

## ZIP Archive Handling

### Research Findings

- **233 ZIP attachments** across the opportunity database (0.5% of all 51,279 attachments)
- **144 opportunities** have at least one ZIP; **25 have ZIPs but NO PDFs** (completely invisible to text extraction without ZIP handling)
- Sample ZIP (INL W-TPC BPA): 3.97 MB compressed → 4.09 MB uncompressed (1:1 ratio), 17 files (9 .docx, 6 .xlsx, 2 .pdf), no nesting, no encryption
- Typical content: SOW sections, pricing sheets, templates, wage determinations, past performance questionnaires bundled into a single archive

### Security Controls

All ZIP extraction goes through `fed_prospector/etl/safe_zip.py`:

| Control | Limit | Why |
|---------|-------|-----|
| Path traversal prevention | Resolve + `is_relative_to()` check | Zip Slip attack (CWE-22) |
| ZIP bomb detection | 100:1 max compression ratio | Decompression bomb (CWE-400) |
| Max total uncompressed size | 500 MB | Disk exhaustion |
| Max single file size | 100 MB | Memory/disk exhaustion |
| Max file count | 500 entries | File count bomb |
| Max nesting depth | 1 level | Recursive nesting bomb (CWE-674) |
| Symlink filtering | Skip symlink entries | Link following attack (CWE-59) |
| File type whitelist | .pdf, .docx, .xlsx, .txt, .csv, .html, .rtf, .pptx only | No executables (CWE-434) |
| Encryption detection | Skip encrypted entries | Can't extract, fail gracefully |

### Integration Approach

**Option A (chosen):** Concatenate all inner file texts into the parent `opportunity_attachment.extracted_text` with section markers:
```
## [SOW_Part1.pdf]

{extracted text}

---

## [Pricing_Sheet.xlsx]

{extracted text}
```

This is simpler than creating separate `opportunity_attachment` rows per inner file and keeps provenance via the section markers. The intel extractor already tracks `char_offset_start`/`char_offset_end` which maps back to the section markers.

### Implementation

- **New module:** `fed_prospector/etl/safe_zip.py` — `extract_zip_safely()` with all safety controls
- **Modified:** `attachment_text_extractor.py` — add ZIP handler that extracts → dispatches each inner file to existing handlers → concatenates results
- **No schema changes** — ZIP contents stored in parent attachment's `extracted_text` column

---

## Out of Scope

- Full-text search across all attachment content (future phase — would need Elasticsearch or similar)
- Original file viewing/preview in UI (store text only in Round 1)
- Embedding-based semantic search (future phase)
- Fine-tuned classification models (overkill at current scale)
- Automated bid/no-bid recommendations (uses intel as input, but decision logic is separate)

---

## Testing Checklist

- [ ] Download attachments for an opportunity with known resource_links
- [ ] Extract text from PDF (text-based and scanned)
- [ ] Extract text from Word document
- [ ] Extract text from Excel spreadsheet
- [ ] Keyword extraction correctly identifies security clearance requirements
- [ ] Keyword extraction correctly identifies LPTA vs Best Value
- [ ] Keyword extraction correctly identifies contract vehicle types
- [ ] Keyword extraction correctly identifies recompete/incumbent information
- [ ] False positive filtering works (e.g., "Secretary" doesn't match "Secret")
- [ ] Confidence scoring reflects match quality
- [ ] Reserved opportunity columns populated from intel
- [ ] Claude Batch API integration sends and receives correctly (Round 3)
- [ ] On-demand analysis endpoint works (Round 3)
- [ ] UI displays extracted intelligence with confidence indicators (Round 4)
- [ ] Large file handling (skip files > max size)
- [ ] Idempotent re-runs don't duplicate data (hash-based skip)
- [ ] Re-download triggers re-extraction when content_hash changes
- [ ] `--force` flag bypasses hash check for re-processing
- [ ] Every extracted intel field has at least one source record in `opportunity_intel_source`
- [ ] Source records include filename, page number, matched text, and surrounding context
- [ ] UI "View Source" shows highlighted match in context
- [ ] AI extraction returns evidence quotes that populate source records
- [ ] False positive scenario: "Secretary" match is reviewable via source context

---

## Example: Dept of State INL Worldwide (W-TPC BPA) PR15796090

This real opportunity illustrates why attachment intelligence matters:

1. **Security Clearance**: SOW mentions "Active Secret Security Clearance" — but is that a Facility Clearance (company must hold FCL) or Personnel Clearance (individual employees need PCL)? Keyword extraction finds "Active Secret Security Clearance" + context; AI analysis can determine scope.

2. **Scope Summary**: Without reading the full SOW, decision-makers need a 2-3 sentence summary of what the work actually involves.

3. **Vehicle Type**: Is this a BPA call? Under what contract vehicle? The "BPA" in the title suggests Blanket Purchase Agreement — keyword extraction confirms.

4. **Evaluation Method**: LPTA means lowest price wins; Best Value means past performance matters. This changes bid strategy entirely.

All of this is in the attachments, not the opportunity metadata.

---

## Task Summary

| # | Task | Layer | Complexity | Round | Depends On |
|---|------|-------|-----------|-------|------------|
| 1 | Attachment storage schema (`opportunity_attachment` table) | Backend | Low | 1 | — |
| 2 | Attachment downloader module + CLI | Backend | Medium | 1 | 1 |
| 3 | Text extraction engine (PDF, Word, Excel, OCR) | Backend | Medium | 1 | 1, 2 |
| 4 | Regex/keyword intelligence extractor + `opportunity_attachment_intel` + `opportunity_intel_source` tables | Backend | High | 2 | 3 |
| 5 | Populate reserved opportunity columns from intel | Backend | Low | 2 | 4 |
| 6 | Claude Batch API integration for AI analysis | Python | High | 3 | 3 |
| 7 | On-demand analysis endpoint (`POST .../analyze`) + read endpoint (`GET .../document-intelligence`) + DTOs + `AttachmentIntelService` + EF Core entities | C# API | Medium | 3 | 4, 6 |
| 8 | Document Intelligence tab (intel display, provenance sources, "Analyze" button, attachment list) | React UI | Medium | 4 | 7 |
