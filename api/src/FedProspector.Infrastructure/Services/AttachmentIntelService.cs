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
        // Fetch all attachments for this opportunity
        var attachments = await _context.OpportunityAttachments.AsNoTracking()
            .Where(a => a.NoticeId == noticeId)
            .ToListAsync();

        if (attachments.Count == 0)
            return null;

        // Fetch all intel records for this opportunity
        var intelRecords = await _context.OpportunityAttachmentIntels.AsNoTracking()
            .Where(i => i.NoticeId == noticeId)
            .ToListAsync();

        // Build attachment lookup by ID
        var attachmentLookup = attachments.ToDictionary(a => a.AttachmentId);

        // Fetch sources from ALL intel records (Problem 1: merged sources)
        List<OpportunityIntelSource> sources = [];
        if (intelRecords.Count > 0)
        {
            var allIntelIds = intelRecords.Select(i => i.IntelId).ToList();
            sources = await _context.OpportunityIntelSources.AsNoTracking()
                .Where(s => allIntelIds.Contains(s.IntelId))
                .ToListAsync();
        }

        // Available extraction methods (Problem 1)
        var availableMethods = intelRecords
            .Where(i => !string.IsNullOrEmpty(i.ExtractionMethod))
            .Select(i => i.ExtractionMethod!)
            .Distinct()
            .OrderBy(m => ExtractionMethodPriority.GetValueOrDefault(m, 0))
            .ToList();

        // Best intel record by method priority (for LatestExtractionMethod, LastExtractedAt)
        var bestIntel = intelRecords
            .OrderByDescending(i => ExtractionMethodPriority.GetValueOrDefault(i.ExtractionMethod ?? "", 0))
            .ThenByDescending(i => i.ExtractedAt)
            .FirstOrDefault();

        // Problem 5: Cross-attachment aggregation with domain-specific rules
        var clearanceRequired = AggregateBooleanYWins(intelRecords, i => i.ClearanceRequired);
        var clearanceLevel = AggregateClearanceLevel(intelRecords, clearanceRequired);
        var clearanceScope = AggregatePreferLongest(intelRecords, i => i.ClearanceScope);
        var evalMethod = AggregatePreferMostSpecific(intelRecords, i => i.EvalMethod);
        var vehicleType = AggregatePreferMostSpecific(intelRecords, i => i.VehicleType);
        var isRecompete = AggregateBooleanYWins(intelRecords, i => i.IsRecompete);
        var incumbentName = AggregatePreferShortest(intelRecords, i => i.IncumbentName);
        var scopeSummary = AggregatePreferLongestFromBestConfidence(intelRecords, i => i.ScopeSummary);
        var periodOfPerformance = AggregatePeriodOfPerformance(intelRecords);
        var pricingStructure = AggregatePreferMostSpecific(intelRecords, i => i.PricingStructure);
        var placeOfPerformance = AggregatePreferLongest(intelRecords, i => i.PlaceOfPerformance);

        // Aggregate labor categories and key requirements from all records
        var laborCategories = intelRecords
            .SelectMany(i => DeserializeJsonList(i.LaborCategories))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToList();
        var keyRequirements = intelRecords
            .SelectMany(i => DeserializeJsonList(i.KeyRequirements))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToList();

        // Problem 2: Confidence from best intel record by method priority
        var confidenceRecord = intelRecords
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

        // Problem 6: Detail text fields from AI records only
        var aiRecords = intelRecords
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

        // Problem 7: Per-attachment drill-down
        var perAttachmentIntel = BuildPerAttachmentBreakdown(intelRecords, attachmentLookup);

        var analyzedCount = attachments.Count(a =>
            a.ExtractionStatus == "extracted" || a.ExtractionStatus == "analyzed");

        var dto = new DocumentIntelligenceDto
        {
            NoticeId = noticeId,
            AttachmentCount = attachments.Count,
            AnalyzedCount = analyzedCount,
            LatestExtractionMethod = bestIntel?.ExtractionMethod,
            LastExtractedAt = bestIntel?.ExtractedAt,
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
            Sources = sources.Select(s => new IntelSourceDto
            {
                FieldName = s.FieldName,
                SourceFilename = s.SourceFilename,
                PageNumber = s.PageNumber,
                MatchedText = s.MatchedText,
                SurroundingContext = s.SurroundingContext,
                ExtractionMethod = s.ExtractionMethod ?? "",
                Confidence = s.Confidence ?? ""
            }).ToList(),
            Attachments = attachments.Select(a => new AttachmentSummaryDto
            {
                AttachmentId = a.AttachmentId,
                Filename = a.Filename ?? "",
                Url = a.Url,
                ContentType = a.ContentType,
                FileSizeBytes = a.FileSizeBytes,
                PageCount = a.PageCount,
                DownloadStatus = a.DownloadStatus,
                ExtractionStatus = a.ExtractionStatus,
                SkipReason = a.SkipReason
            }).ToList(),
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

    public async Task<AnalysisEstimateDto> GetAnalysisEstimateAsync(string noticeId, string model = "haiku")
    {
        const int maxCharsPerDoc = 100_000;
        const int systemPromptTokensPerDoc = 800;
        const int maxOutputTokensPerDoc = 2000;

        // Get all complete attachments for this notice
        var attachments = await _context.OpportunityAttachments.AsNoTracking()
            .Where(a => a.NoticeId == noticeId && a.ExtractionStatus == "extracted")
            .Select(a => new
            {
                a.AttachmentId,
                TextLength = a.ExtractedText != null ? a.ExtractedText.Length : 0
            })
            .ToListAsync();

        // Get attachment IDs that already have AI analysis (excluding dry runs)
        var analyzedAttachmentIds = await _context.OpportunityAttachmentIntels.AsNoTracking()
            .Where(i => i.NoticeId == noticeId
                && i.AttachmentId != null
                && i.ExtractionMethod != null
                && i.ExtractionMethod.StartsWith("ai_")
                && i.ExtractionMethod != "ai_dry_run")
            .Select(i => i.AttachmentId!.Value)
            .Distinct()
            .ToListAsync();

        var analyzedSet = new HashSet<int>(analyzedAttachmentIds);
        var totalAttachments = attachments.Count;
        var alreadyAnalyzed = attachments.Count(a => analyzedSet.Contains(a.AttachmentId));
        var remaining = totalAttachments - alreadyAnalyzed;

        var totalChars = attachments
            .Where(a => !analyzedSet.Contains(a.AttachmentId))
            .Sum(a => Math.Min(a.TextLength, maxCharsPerDoc));

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
            AttachmentCount = totalAttachments,
            TotalChars = totalChars,
            EstimatedInputTokens = estimatedInputTokens,
            EstimatedOutputTokens = estimatedOutputTokens,
            EstimatedCostUsd = Math.Round(estimatedCost, 6),
            Model = model.ToLowerInvariant() == "sonnet" ? "sonnet" : "haiku",
            AlreadyAnalyzed = alreadyAnalyzed,
            RemainingToAnalyze = remaining
        };
    }

    // --- Aggregation helpers (Problem 5) ---

    /// <summary>Returns true-ish value if it's not a null equivalent.</summary>
    private static string? NormalizeValue(string? value)
    {
        if (value == null) return null;
        var trimmed = value.Trim();
        return NullEquivalents.Contains(trimmed) ? null : trimmed;
    }

    /// <summary>"Y" wins over "N" wins over null.</summary>
    private static string? AggregateBooleanYWins(
        List<OpportunityAttachmentIntel> records, Func<OpportunityAttachmentIntel, string?> selector)
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
        List<OpportunityAttachmentIntel> records, string? aggregatedClearanceRequired)
    {
        // Only consider clearance levels from records that say clearance is required
        var candidates = records;
        if (string.Equals(aggregatedClearanceRequired, "Y", StringComparison.OrdinalIgnoreCase))
        {
            candidates = records
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
        List<OpportunityAttachmentIntel> records, Func<OpportunityAttachmentIntel, string?> selector)
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
        List<OpportunityAttachmentIntel> records, Func<OpportunityAttachmentIntel, string?> selector)
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
        List<OpportunityAttachmentIntel> records, Func<OpportunityAttachmentIntel, string?> selector)
    {
        // "Most specific" = longest non-null value, as specific values like "LPTA" or "Best Value"
        // are more informative than generic ones
        return AggregatePreferLongest(records, selector);
    }

    /// <summary>Prefer longest from highest-confidence record.</summary>
    private static string? AggregatePreferLongestFromBestConfidence(
        List<OpportunityAttachmentIntel> records, Func<OpportunityAttachmentIntel, string?> selector)
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
    private static string? AggregatePeriodOfPerformance(List<OpportunityAttachmentIntel> records)
    {
        // NormalizeValue already strips "not specified" etc.
        // Among remaining values, prefer the longest (most detail)
        return AggregatePreferLongest(records, i => i.PeriodOfPerformance);
    }

    /// <summary>Get detail text from AI records only, preferring highest method priority then most recent.</summary>
    private static string? AggregateDetailField(
        List<OpportunityAttachmentIntel> aiRecords, Func<OpportunityAttachmentIntel, string?> selector)
    {
        // aiRecords are already sorted by method priority desc, then extractedAt desc
        foreach (var r in aiRecords)
        {
            var val = NormalizeValue(selector(r));
            if (val != null) return val;
        }
        return null;
    }

    /// <summary>Build per-attachment breakdown for Problem 7.</summary>
    private static List<AttachmentIntelBreakdownDto> BuildPerAttachmentBreakdown(
        List<OpportunityAttachmentIntel> intelRecords,
        Dictionary<int, OpportunityAttachment> attachmentLookup)
    {
        // Group intel records by attachment_id, pick best per attachment
        var result = new List<AttachmentIntelBreakdownDto>();

        var grouped = intelRecords
            .Where(i => i.AttachmentId.HasValue)
            .GroupBy(i => i.AttachmentId!.Value);

        foreach (var group in grouped)
        {
            var best = group
                .OrderByDescending(i => ExtractionMethodPriority.GetValueOrDefault(i.ExtractionMethod ?? "", 0))
                .ThenByDescending(i => i.ExtractedAt)
                .First();

            var filename = attachmentLookup.TryGetValue(group.Key, out var att)
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
