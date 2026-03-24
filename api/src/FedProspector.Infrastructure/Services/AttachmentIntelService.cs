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

        // Pick the best intel record by extraction method priority
        var bestIntel = intelRecords
            .OrderByDescending(i => ExtractionMethodPriority.GetValueOrDefault(i.ExtractionMethod ?? "", 0))
            .ThenByDescending(i => i.ExtractedAt)
            .FirstOrDefault();

        // Fetch sources for the best intel record
        List<OpportunityIntelSource> sources = [];
        if (bestIntel != null)
        {
            sources = await _context.OpportunityIntelSources.AsNoTracking()
                .Where(s => s.IntelId == bestIntel.IntelId)
                .ToListAsync();
        }

        var analyzedCount = attachments.Count(a =>
            a.ExtractionStatus == "extracted" || a.ExtractionStatus == "analyzed");

        var dto = new DocumentIntelligenceDto
        {
            NoticeId = noticeId,
            AttachmentCount = attachments.Count,
            AnalyzedCount = analyzedCount,
            LatestExtractionMethod = bestIntel?.ExtractionMethod,
            LastExtractedAt = bestIntel?.ExtractedAt,
            ClearanceRequired = bestIntel?.ClearanceRequired,
            ClearanceLevel = bestIntel?.ClearanceLevel,
            ClearanceScope = bestIntel?.ClearanceScope,
            EvalMethod = bestIntel?.EvalMethod,
            VehicleType = bestIntel?.VehicleType,
            IsRecompete = bestIntel?.IsRecompete,
            IncumbentName = bestIntel?.IncumbentName,
            ScopeSummary = bestIntel?.ScopeSummary,
            PeriodOfPerformance = bestIntel?.PeriodOfPerformance,
            LaborCategories = DeserializeJsonList(bestIntel?.LaborCategories),
            KeyRequirements = DeserializeJsonList(bestIntel?.KeyRequirements),
            OverallConfidence = bestIntel?.OverallConfidence ?? "low",
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
                ContentType = a.ContentType,
                FileSizeBytes = a.FileSizeBytes,
                PageCount = a.PageCount,
                DownloadStatus = a.DownloadStatus,
                ExtractionStatus = a.ExtractionStatus,
                SkipReason = a.SkipReason
            }).ToList()
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
