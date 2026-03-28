using System.Text.Json;
using FedProspector.Core.DTOs.Awards;
using FedProspector.Core.DTOs.Intelligence;
using FedProspector.Core.Interfaces;
using FedProspector.Core.Models;
using FedProspector.Infrastructure.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;

namespace FedProspector.Infrastructure.Services;

public class AttachmentIntelService : IAttachmentIntelService
{
    private readonly FedProspectorDbContext _context;
    private readonly ILogger<AttachmentIntelService> _logger;

    // Extraction method priority: higher = better
    private static readonly Dictionary<string, int> ExtractionMethodPriority = new()
    {
        ["ai_sonnet"] = 4,
        ["ai_haiku"] = 3,
        ["heuristic"] = 2,
        ["keyword"] = 1
    };

    // Clearance level hierarchy: higher index = higher clearance
    private static readonly List<string> ClearanceLevelHierarchy = new()
    {
        "public trust",
        "confidential",
        "secret",
        "top secret",
        "ts/sci"
    };

    // Strings treated as null equivalents during aggregation
    private static readonly HashSet<string> NullEquivalents = new(StringComparer.OrdinalIgnoreCase)
    {
        "not specified",
        "n/a",
        "none",
        "not applicable",
        "not specified in q&a document",
        ""
    };

    public AttachmentIntelService(FedProspectorDbContext context, ILogger<AttachmentIntelService> logger)
    {
        _context = context;
        _logger = logger;
    }

    public async Task<DocumentIntelligenceDto?> GetDocumentIntelligenceAsync(string noticeId)
    {
        // Fetch attachment mappings for this opportunity via the join table
        var mappings = await _context.OpportunityAttachments.AsNoTracking()
            .Where(m => m.NoticeId == noticeId)
            .ToListAsync();

        if (mappings.Count == 0)
            return null;

        var attachmentIds = mappings.Select(m => m.AttachmentId).Distinct().ToList();

        // Fetch SamAttachment details for these attachments
        var samAttachments = await _context.SamAttachments.AsNoTracking()
            .Where(a => attachmentIds.Contains(a.AttachmentId))
            .ToListAsync();

        var samAttachmentLookup = samAttachments.ToDictionary(a => a.AttachmentId);

        // Fetch documents for these attachments
        var documents = await _context.AttachmentDocuments.AsNoTracking()
            .Where(d => attachmentIds.Contains(d.AttachmentId))
            .ToListAsync();

        var documentIds = documents.Select(d => d.DocumentId).ToList();

        // Fetch per-document intel summaries
        var intelRecords = await _context.DocumentIntelSummaries.AsNoTracking()
            .Where(i => documentIds.Contains(i.DocumentId))
            .ToListAsync();

        // Fetch per-opportunity rollup summaries
        var summaryRecords = await _context.OpportunityAttachmentSummaries.AsNoTracking()
            .Where(s => s.NoticeId == noticeId)
            .ToListAsync();

        // Fetch evidence from per-document intel records
        List<DocumentIntelEvidence> evidence = [];
        if (intelRecords.Count > 0)
        {
            var allIntelIds = intelRecords.Select(i => i.IntelId).ToList();
            evidence = await _context.DocumentIntelEvidence.AsNoTracking()
                .Where(e => allIntelIds.Contains(e.IntelId))
                .ToListAsync();
        }

        // Use summary records for aggregated intel (replaces old NULL-attachment consolidated rows)
        // Fall back to per-document intel if no summaries exist yet
        var aggregationRecords = summaryRecords.Count > 0 ? summaryRecords : null;

        // Available extraction methods
        var availableMethods = (aggregationRecords ?? (IEnumerable<IIntelFields>)intelRecords)
            .Where(i => !string.IsNullOrEmpty(i.ExtractionMethod))
            .Select(i => i.ExtractionMethod!)
            .Distinct()
            .OrderBy(m => ExtractionMethodPriority.GetValueOrDefault(m, 0))
            .ToList();

        // Best record by method priority (for LatestExtractionMethod, LastExtractedAt)
        var bestRecord = (aggregationRecords ?? (IEnumerable<IIntelFields>)intelRecords)
            .OrderByDescending(i => ExtractionMethodPriority.GetValueOrDefault(i.ExtractionMethod ?? "", 0))
            .ThenByDescending(i => i.ExtractedAt)
            .FirstOrDefault();

        // Cross-document aggregation with domain-specific rules
        var recordsForAgg = aggregationRecords ?? (IReadOnlyList<IIntelFields>)intelRecords;
        var clearanceRequired = AggregateBooleanYWins(recordsForAgg, i => i.ClearanceRequired);
        var clearanceLevel = AggregateClearanceLevel(recordsForAgg, clearanceRequired);
        var clearanceScope = AggregatePreferLongest(recordsForAgg, i => i.ClearanceScope);
        var evalMethod = AggregatePreferMostSpecific(recordsForAgg, i => i.EvalMethod);
        var vehicleType = AggregatePreferMostSpecific(recordsForAgg, i => i.VehicleType);
        var isRecompete = AggregateBooleanYWins(recordsForAgg, i => i.IsRecompete);
        var incumbentName = AggregatePreferShortest(recordsForAgg, i => i.IncumbentName);
        var scopeSummary = AggregatePreferLongestFromBestConfidence(recordsForAgg, i => i.ScopeSummary);
        var periodOfPerformance = AggregatePeriodOfPerformance(recordsForAgg);
        var pricingStructure = AggregatePreferMostSpecific(recordsForAgg, i => i.PricingStructure);
        var placeOfPerformance = AggregatePreferLongest(recordsForAgg, i => i.PlaceOfPerformance);

        // Aggregate labor categories and key requirements from all records
        var laborCategories = recordsForAgg
            .SelectMany(i => DeserializeJsonList(i.LaborCategories))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToList();
        var keyRequirements = recordsForAgg
            .SelectMany(i => DeserializeJsonList(i.KeyRequirements))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToList();

        // Confidence from best record by method priority
        var confidenceRecord = recordsForAgg
            .Where(i => !string.IsNullOrEmpty(i.OverallConfidence))
            .OrderByDescending(i => ExtractionMethodPriority.GetValueOrDefault(i.ExtractionMethod ?? "", 0))
            .ThenByDescending(i => i.ExtractedAt)
            .FirstOrDefault();

        var overallConfidence = confidenceRecord?.OverallConfidence ?? "low";
        Dictionary<string, string>? confidenceDetails = null;
        if (!string.IsNullOrEmpty(confidenceRecord?.ConfidenceDetails))
        {
            try
            {
                confidenceDetails = JsonSerializer.Deserialize<Dictionary<string, string>>(confidenceRecord.ConfidenceDetails);
            }
            catch
            {
                // Malformed JSON — leave null
            }
        }

        // Detail text fields from AI records only
        var aiRecords = recordsForAgg
            .Where(i => i.ExtractionMethod is "ai_haiku" or "ai_sonnet")
            .OrderByDescending(i => ExtractionMethodPriority.GetValueOrDefault(i.ExtractionMethod ?? "", 0))
            .ThenByDescending(i => i.ExtractedAt)
            .ToList();

        var clearanceDetails = AggregateDetailField(aiRecords, i => i.ClearanceDetails);
        var evalDetails = AggregateDetailField(aiRecords, i => i.EvalDetails);
        var vehicleDetails = AggregateDetailField(aiRecords, i => i.VehicleDetails);
        var recompeteDetails = AggregateDetailField(aiRecords, i => i.RecompeteDetails);
        // No dedicated DB columns for pricing_details / pop_details — leave null for now
        string? pricingDetails = null;
        string? popDetails = null;

        // Build merged source passages (server-side merge of nearby keyword matches)
        var mergedPassages = await BuildMergedPassagesAsync(evidence);

        // Per-attachment drill-down using per-document intel
        var documentLookup = documents.ToDictionary(d => d.DocumentId);
        var perAttachmentIntel = BuildPerAttachmentBreakdown(intelRecords, documents, samAttachmentLookup);

        var analyzedCount = documents.Count(d =>
            d.ExtractionStatus == "extracted");

        var dto = new DocumentIntelligenceDto
        {
            NoticeId = noticeId,
            AttachmentCount = samAttachments.Count,
            AnalyzedCount = analyzedCount,
            LatestExtractionMethod = bestRecord?.ExtractionMethod,
            LastExtractedAt = bestRecord?.ExtractedAt,
            ClearanceRequired = clearanceRequired,
            ClearanceLevel = clearanceLevel,
            ClearanceScope = clearanceScope,
            EvalMethod = evalMethod,
            VehicleType = vehicleType,
            IsRecompete = isRecompete,
            IncumbentName = incumbentName,
            ScopeSummary = scopeSummary,
            PeriodOfPerformance = periodOfPerformance,
            PricingStructure = pricingStructure,
            PlaceOfPerformance = placeOfPerformance,
            LaborCategories = laborCategories,
            KeyRequirements = keyRequirements,
            OverallConfidence = overallConfidence,
            AvailableMethods = availableMethods,
            ConfidenceDetails = confidenceDetails,
            ClearanceDetails = clearanceDetails,
            EvalDetails = evalDetails,
            VehicleDetails = vehicleDetails,
            RecompeteDetails = recompeteDetails,
            PricingDetails = pricingDetails,
            PopDetails = popDetails,
            Sources = evidence.Select(e => new IntelSourceDto
            {
                FieldName = e.FieldName,
                SourceFilename = e.SourceFilename,
                PageNumber = e.PageNumber,
                MatchedText = e.MatchedText,
                SurroundingContext = e.SurroundingContext,
                CharOffsetStart = e.CharOffsetStart,
                CharOffsetEnd = e.CharOffsetEnd,
                ExtractionMethod = e.ExtractionMethod ?? "",
                Confidence = e.Confidence ?? ""
            }).ToList(),
            Attachments = samAttachments.Select(a => new AttachmentSummaryDto
            {
                AttachmentId = a.AttachmentId,
                ResourceGuid = a.ResourceGuid,
                Filename = a.Filename ?? "",
                Url = a.Url,
                ContentType = documents.FirstOrDefault(d => d.AttachmentId == a.AttachmentId)?.ContentType,
                FileSizeBytes = a.FileSizeBytes,
                PageCount = documents.FirstOrDefault(d => d.AttachmentId == a.AttachmentId)?.PageCount,
                DownloadStatus = a.DownloadStatus,
                ExtractionStatus = documents.FirstOrDefault(d => d.AttachmentId == a.AttachmentId)?.ExtractionStatus ?? "pending",
                SkipReason = a.SkipReason
            }).ToList(),
            MergedPassages = mergedPassages,
            PerAttachmentIntel = perAttachmentIntel
        };

        return dto;
    }

    public async Task<LoadRequestStatusDto> RequestAnalysisAsync(string noticeId, string tier, int? userId)
    {
        var requestType = "ATTACHMENT_ANALYSIS";

        // Check for existing pending/processing request
        var existing = await _context.DataLoadRequests.FirstOrDefaultAsync(r =>
            r.LookupKey == noticeId &&
            r.RequestType == requestType &&
            (r.Status == "PENDING" || r.Status == "PROCESSING"));

        if (existing != null)
        {
            return new LoadRequestStatusDto
            {
                RequestId = existing.RequestId,
                RequestType = existing.RequestType,
                Status = existing.Status,
                RequestedAt = existing.RequestedAt,
                ErrorMessage = existing.ErrorMessage
            };
        }

        // Create new request
        var request = new DataLoadRequest
        {
            RequestType = requestType,
            LookupKey = noticeId,
            LookupKeyType = "NOTICE_ID",
            Status = "PENDING",
            RequestedBy = userId,
            RequestedAt = DateTime.UtcNow,
            ResultSummary = JsonSerializer.Serialize(new { tier })
        };

        _context.DataLoadRequests.Add(request);
        await _context.SaveChangesAsync();

        return new LoadRequestStatusDto
        {
            RequestId = request.RequestId,
            RequestType = request.RequestType,
            Status = request.Status,
            RequestedAt = request.RequestedAt
        };
    }

    public async Task<LoadRequestStatusDto?> GetAnalysisStatusAsync(string noticeId)
    {
        var request = await _context.DataLoadRequests.AsNoTracking()
            .Where(r => r.LookupKey == noticeId && r.RequestType == "ATTACHMENT_ANALYSIS")
            .OrderByDescending(r => r.RequestedAt)
            .FirstOrDefaultAsync();

        if (request == null) return null;

        return new LoadRequestStatusDto
        {
            RequestId = request.RequestId,
            RequestType = request.RequestType,
            Status = request.Status,
            RequestedAt = request.RequestedAt,
            ErrorMessage = request.ErrorMessage
        };
    }

    public async Task<AnalysisEstimateDto> GetAnalysisEstimateAsync(string noticeId, string model = "haiku")
    {
        const int maxCharsPerDoc = 100_000;
        const int systemPromptTokensPerDoc = 800;
        const int maxOutputTokensPerDoc = 2000;

        // Get attachment IDs for this notice via the map table
        var attachmentIds = await _context.OpportunityAttachments.AsNoTracking()
            .Where(m => m.NoticeId == noticeId)
            .Select(m => m.AttachmentId)
            .Distinct()
            .ToListAsync();

        // Get all extracted documents for these attachments
        var documents = await _context.AttachmentDocuments.AsNoTracking()
            .Where(d => attachmentIds.Contains(d.AttachmentId) && d.ExtractionStatus == "extracted")
            .Select(d => new
            {
                d.DocumentId,
                d.AttachmentId,
                TextLength = d.ExtractedText != null ? d.ExtractedText.Length : 0
            })
            .ToListAsync();

        // Get document IDs that already have AI analysis
        var analyzedDocumentIds = await _context.DocumentIntelSummaries.AsNoTracking()
            .Where(i => documents.Select(d => d.DocumentId).Contains(i.DocumentId)
                && i.ExtractionMethod.StartsWith("ai_"))
            .Select(i => i.DocumentId)
            .Distinct()
            .ToListAsync();

        var analyzedSet = new HashSet<int>(analyzedDocumentIds);
        var totalDocuments = documents.Count;
        var alreadyAnalyzed = documents.Count(d => analyzedSet.Contains(d.DocumentId));
        var remaining = totalDocuments - alreadyAnalyzed;

        var totalChars = documents
            .Where(d => !analyzedSet.Contains(d.DocumentId))
            .Sum(d => Math.Min(d.TextLength, maxCharsPerDoc));

        var estimatedInputTokens = totalChars / 4 + systemPromptTokensPerDoc * remaining;
        var estimatedOutputTokens = maxOutputTokensPerDoc * remaining;

        // Pricing per million tokens
        var (inputPricePerMillion, outputPricePerMillion) = model.ToLowerInvariant() switch
        {
            "sonnet" => (3.00m, 15.00m),
            _ => (1.00m, 5.00m)  // haiku default
        };

        var estimatedCost = estimatedInputTokens / 1_000_000m * inputPricePerMillion
                          + estimatedOutputTokens / 1_000_000m * outputPricePerMillion;

        return new AnalysisEstimateDto
        {
            NoticeId = noticeId,
            AttachmentCount = totalDocuments,
            TotalChars = totalChars,
            EstimatedInputTokens = estimatedInputTokens,
            EstimatedOutputTokens = estimatedOutputTokens,
            EstimatedCostUsd = Math.Round(estimatedCost, 6),
            Model = model.ToLowerInvariant() == "sonnet" ? "sonnet" : "haiku",
            AlreadyAnalyzed = alreadyAnalyzed,
            RemainingToAnalyze = remaining
        };
    }

    // --- Aggregation helpers ---

    /// <summary>Returns true-ish value if it's not a null equivalent.</summary>
    private static string? NormalizeValue(string? value)
    {
        if (value == null) return null;
        var trimmed = value.Trim();
        return NullEquivalents.Contains(trimmed) ? null : trimmed;
    }

    /// <summary>"Y" wins over "N" wins over null.</summary>
    private static string? AggregateBooleanYWins(
        IEnumerable<IIntelFields> records, Func<IIntelFields, string?> selector)
    {
        string? best = null;
        foreach (var r in records)
        {
            var val = NormalizeValue(selector(r));
            if (val == null) continue;
            if (string.Equals(val, "Y", StringComparison.OrdinalIgnoreCase))
                return "Y"; // Short-circuit: Y always wins
            best ??= val; // Keep first non-null (e.g., "N")
        }
        return best;
    }

    /// <summary>Highest clearance level wins, only from records where clearance_required = "Y".</summary>
    private static string? AggregateClearanceLevel(
        IEnumerable<IIntelFields> records, string? aggregatedClearanceRequired)
    {
        // Only consider clearance levels from records that say clearance is required
        var candidates = records.ToList();
        if (string.Equals(aggregatedClearanceRequired, "Y", StringComparison.OrdinalIgnoreCase))
        {
            candidates = candidates
                .Where(r => string.Equals(NormalizeValue(r.ClearanceRequired), "Y", StringComparison.OrdinalIgnoreCase))
                .ToList();
        }

        string? best = null;
        int bestRank = -1;
        foreach (var r in candidates)
        {
            var val = NormalizeValue(r.ClearanceLevel);
            if (val == null) continue;
            var rank = ClearanceLevelHierarchy.FindIndex(
                h => val.Contains(h, StringComparison.OrdinalIgnoreCase));
            if (rank > bestRank)
            {
                bestRank = rank;
                best = val;
            }
            else if (rank == -1 && best == null)
            {
                // Unknown level — keep as fallback if nothing ranked found
                best = val;
            }
        }
        return best;
    }

    /// <summary>Prefer the shortest non-null, non-equivalent value (likely the clean name).</summary>
    private static string? AggregatePreferShortest(
        IEnumerable<IIntelFields> records, Func<IIntelFields, string?> selector)
    {
        string? best = null;
        foreach (var r in records)
        {
            var val = NormalizeValue(selector(r));
            if (val == null) continue;
            if (best == null || val.Length < best.Length)
                best = val;
        }
        return best;
    }

    /// <summary>Prefer the longest non-null, non-equivalent value (most detail).</summary>
    private static string? AggregatePreferLongest(
        IEnumerable<IIntelFields> records, Func<IIntelFields, string?> selector)
    {
        string? best = null;
        foreach (var r in records)
        {
            var val = NormalizeValue(selector(r));
            if (val == null) continue;
            if (best == null || val.Length > best.Length)
                best = val;
        }
        return best;
    }

    /// <summary>Prefer the most specific (longest) non-null value — works for eval_method, vehicle_type, pricing.</summary>
    private static string? AggregatePreferMostSpecific(
        IEnumerable<IIntelFields> records, Func<IIntelFields, string?> selector)
    {
        // "Most specific" = longest non-null value, as specific values like "LPTA" or "Best Value"
        // are more informative than generic ones
        return AggregatePreferLongest(records, selector);
    }

    /// <summary>Prefer longest from highest-confidence record.</summary>
    private static string? AggregatePreferLongestFromBestConfidence(
        IEnumerable<IIntelFields> records, Func<IIntelFields, string?> selector)
    {
        // Order by method priority (higher = better confidence), then by value length
        var best = records
            .Select(r => new { Value = NormalizeValue(selector(r)), Record = r })
            .Where(x => x.Value != null)
            .OrderByDescending(x => ExtractionMethodPriority.GetValueOrDefault(x.Record.ExtractionMethod ?? "", 0))
            .ThenByDescending(x => x.Value!.Length)
            .FirstOrDefault();
        return best?.Value;
    }

    /// <summary>Prefer values with actual durations, reject "not specified" variants.</summary>
    private static string? AggregatePeriodOfPerformance(IEnumerable<IIntelFields> records)
    {
        // NormalizeValue already strips "not specified" etc.
        // Among remaining values, prefer the longest (most detail)
        return AggregatePreferLongest(records, i => i.PeriodOfPerformance);
    }

    /// <summary>Get detail text from AI records only, preferring highest method priority then most recent.</summary>
    private static string? AggregateDetailField(
        IEnumerable<IIntelFields> aiRecords, Func<IIntelFields, string?> selector)
    {
        // aiRecords are already sorted by method priority desc, then extractedAt desc
        foreach (var r in aiRecords)
        {
            var val = NormalizeValue(selector(r));
            if (val != null) return val;
        }
        return null;
    }

    /// <summary>Build per-attachment breakdown using per-document intel.</summary>
    private static List<AttachmentIntelBreakdownDto> BuildPerAttachmentBreakdown(
        List<DocumentIntelSummary> intelRecords,
        List<AttachmentDocument> documents,
        Dictionary<int, SamAttachment> samAttachmentLookup)
    {
        var result = new List<AttachmentIntelBreakdownDto>();

        // Build document-to-attachment lookup
        var docToAttachment = documents.ToDictionary(d => d.DocumentId, d => d.AttachmentId);

        // Group intel records by attachment_id (via document -> attachment mapping)
        var grouped = intelRecords
            .Where(i => docToAttachment.ContainsKey(i.DocumentId))
            .GroupBy(i => docToAttachment[i.DocumentId]);

        foreach (var group in grouped)
        {
            var best = group
                .OrderByDescending(i => ExtractionMethodPriority.GetValueOrDefault(i.ExtractionMethod ?? "", 0))
                .ThenByDescending(i => i.ExtractedAt)
                .First();

            var filename = samAttachmentLookup.TryGetValue(group.Key, out var att)
                ? att.Filename ?? ""
                : "";

            result.Add(new AttachmentIntelBreakdownDto
            {
                AttachmentId = group.Key,
                Filename = filename,
                ExtractionMethod = best.ExtractionMethod ?? "",
                Confidence = best.OverallConfidence,
                ClearanceRequired = NormalizeValue(best.ClearanceRequired),
                ClearanceLevel = NormalizeValue(best.ClearanceLevel),
                EvalMethod = NormalizeValue(best.EvalMethod),
                VehicleType = NormalizeValue(best.VehicleType),
                IsRecompete = NormalizeValue(best.IsRecompete),
                IncumbentName = NormalizeValue(best.IncumbentName),
                PricingStructure = NormalizeValue(best.PricingStructure),
                PlaceOfPerformance = NormalizeValue(best.PlaceOfPerformance)
            });
        }

        return result;
    }

    // --- Merged source passages ---

    private const int MergeGap = 250;
    private const int ContextBorder = 150;

    /// <summary>
    /// Merge nearby keyword evidence from the same document into single text passages
    /// with multiple highlights, slicing from the document's ExtractedText.
    /// </summary>
    private async Task<List<MergedSourcePassageDto>> BuildMergedPassagesAsync(
        List<DocumentIntelEvidence> evidence)
    {
        // Only keyword evidence with char offsets can be merged
        var keywordEvidence = evidence
            .Where(e => e.CharOffsetStart.HasValue
                        && !(e.ExtractionMethod ?? "").StartsWith("ai_"))
            .ToList();

        if (keywordEvidence.Count == 0)
            return [];

        // Get distinct document IDs we need text for
        var documentIds = keywordEvidence
            .Where(e => e.DocumentId.HasValue)
            .Select(e => e.DocumentId!.Value)
            .Distinct()
            .ToList();

        // Fetch only DocumentId + ExtractedText (text can be huge, skip other columns)
        var textLookup = await _context.AttachmentDocuments.AsNoTracking()
            .Where(d => documentIds.Contains(d.DocumentId))
            .Select(d => new { d.DocumentId, d.ExtractedText })
            .ToDictionaryAsync(d => d.DocumentId, d => d.ExtractedText);

        // Group by (FieldName, SourceFilename)
        var grouped = keywordEvidence
            .GroupBy(e => (e.FieldName, Filename: e.SourceFilename ?? ""));

        var passages = new List<MergedSourcePassageDto>();

        foreach (var group in grouped)
        {
            var sorted = group.OrderBy(e => e.CharOffsetStart!.Value).ToList();

            // Cluster: merge evidence where gap <= MergeGap
            var clusters = new List<List<DocumentIntelEvidence>>();
            var currentCluster = new List<DocumentIntelEvidence> { sorted[0] };

            for (int i = 1; i < sorted.Count; i++)
            {
                var prev = currentCluster[^1];
                var prevEnd = prev.CharOffsetEnd ?? (prev.CharOffsetStart!.Value + (prev.MatchedText?.Length ?? 0));
                var currStart = sorted[i].CharOffsetStart!.Value;

                if (currStart - prevEnd <= MergeGap)
                {
                    currentCluster.Add(sorted[i]);
                }
                else
                {
                    clusters.Add(currentCluster);
                    currentCluster = [sorted[i]];
                }
            }
            clusters.Add(currentCluster);

            foreach (var cluster in clusters)
            {
                // Find the document text for this cluster
                var documentId = cluster[0].DocumentId;
                if (documentId == null || !textLookup.TryGetValue(documentId.Value, out var extractedText)
                    || string.IsNullOrEmpty(extractedText))
                {
                    continue; // Skip — no text available
                }

                var textLength = extractedText.Length;

                var minStart = cluster.Min(e => e.CharOffsetStart!.Value) - ContextBorder;
                var maxEnd = cluster.Max(e =>
                    e.CharOffsetEnd ?? (e.CharOffsetStart!.Value + (e.MatchedText?.Length ?? 0))) + ContextBorder;

                // Clamp to valid range
                if (minStart < 0) minStart = 0;
                if (maxEnd > textLength) maxEnd = textLength;

                var textSlice = extractedText[minStart..maxEnd];

                // Build highlights: offset relative to the slice
                var highlights = new List<HighlightSpan>();
                foreach (var src in cluster)
                {
                    var hStart = src.CharOffsetStart!.Value - minStart;
                    var hEnd = (src.CharOffsetEnd ?? (src.CharOffsetStart!.Value + (src.MatchedText?.Length ?? 0))) - minStart;

                    // Clamp highlight to slice bounds
                    if (hStart < 0) hStart = 0;
                    if (hEnd > textSlice.Length) hEnd = textSlice.Length;
                    if (hStart >= hEnd) continue;

                    highlights.Add(new HighlightSpan
                    {
                        Start = hStart,
                        End = hEnd,
                        MatchedText = src.MatchedText ?? textSlice[hStart..hEnd]
                    });
                }

                passages.Add(new MergedSourcePassageDto
                {
                    FieldName = group.Key.FieldName,
                    Filename = group.Key.Filename,
                    PageNumber = cluster[0].PageNumber,
                    Methods = cluster.Select(e => e.ExtractionMethod ?? "keyword").Distinct().ToList(),
                    Confidences = cluster.Select(e => e.Confidence).Where(c => !string.IsNullOrEmpty(c)).Select(c => c!).Distinct().ToList(),
                    Text = textSlice,
                    Highlights = highlights.OrderBy(h => h.Start).ToList(),
                    MatchCount = cluster.Count
                });
            }
        }

        return passages;
    }

    private static List<string> DeserializeJsonList(string? json)
    {
        if (string.IsNullOrWhiteSpace(json))
            return [];

        try
        {
            return JsonSerializer.Deserialize<List<string>>(json) ?? [];
        }
        catch
        {
            return [];
        }
    }
}
