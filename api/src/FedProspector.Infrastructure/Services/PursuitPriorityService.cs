using FedProspector.Core.DTOs.Intelligence;
using FedProspector.Core.Interfaces;
using Microsoft.Extensions.Logging;

namespace FedProspector.Infrastructure.Services;

public class PursuitPriorityService : IPursuitPriorityService
{
    private readonly IPWinService _pwinService;
    private readonly IRecommendedOpportunityService _recommendedService;
    private readonly ILogger<PursuitPriorityService> _logger;

    public PursuitPriorityService(
        IPWinService pwinService,
        IRecommendedOpportunityService recommendedService,
        ILogger<PursuitPriorityService> logger)
    {
        _pwinService = pwinService;
        _recommendedService = recommendedService;
        _logger = logger;
    }

    public async Task<PursuitPriorityDto> CalculateAsync(string noticeId, int orgId)
    {
        // Get pWin and OQS in parallel
        var pwinTask = _pwinService.CalculateAsync(noticeId, orgId);
        var oqTask = _recommendedService.CalculateOqScoreAsync(noticeId, orgId);

        await Task.WhenAll(pwinTask, oqTask);

        var pwin = pwinTask.Result;
        var oq = oqTask.Result;

        var pwinScore = pwin.Score;
        var pwinConfidence = pwin.Confidence;
        var oqScore = oq?.OqScore ?? 0m;
        var oqConfidence = oq?.Confidence ?? "Low";

        return BuildDto(noticeId, pwinScore, pwinConfidence, oqScore, oqConfidence);
    }

    public async Task<List<PursuitPriorityDto>> CalculateBatchAsync(List<string> noticeIds, int orgId)
    {
        var results = new List<PursuitPriorityDto>();

        // Process each notice — could be parallelized further but DB context is scoped
        foreach (var noticeId in noticeIds)
        {
            try
            {
                var dto = await CalculateAsync(noticeId, orgId);
                results.Add(dto);
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "Failed to calculate pursuit priority for {NoticeId}", noticeId);
                // Return a zero-score entry so callers know it was attempted
                results.Add(new PursuitPriorityDto
                {
                    NoticeId = noticeId,
                    PursuitScore = 0,
                    Category = "Skip",
                    PWinConfidence = "Low",
                    OqConfidence = "Low",
                    ConfidenceDiscountApplied = true,
                    Quadrant = "LowPWin_LowOQS"
                });
            }
        }

        return results.OrderByDescending(r => r.PursuitScore).ToList();
    }

    private static PursuitPriorityDto BuildDto(
        string noticeId, decimal pwinScore, string pwinConfidence,
        decimal oqScore, string oqConfidence)
    {
        // Formula: (pWin * 0.6) + (OQS * 0.4)
        var pursuitScore = (pwinScore * 0.6m) + (oqScore * 0.4m);

        // Low-confidence discount: 15%
        var discountApplied = string.Equals(pwinConfidence, "Low", StringComparison.OrdinalIgnoreCase)
                              || string.Equals(oqConfidence, "Low", StringComparison.OrdinalIgnoreCase);
        if (discountApplied)
            pursuitScore *= 0.85m;

        pursuitScore = Math.Round(pursuitScore, 1);

        // Quadrant: pWin >= 50 = High, OQS >= 50 = High
        var pwinHigh = pwinScore >= 50;
        var oqHigh = oqScore >= 50;
        var quadrant = (pwinHigh, oqHigh) switch
        {
            (true, true) => "HighPWin_HighOQS",
            (true, false) => "HighPWin_LowOQS",
            (false, true) => "LowPWin_HighOQS",
            (false, false) => "LowPWin_LowOQS"
        };

        // Category
        var category = pursuitScore switch
        {
            >= 75 => "MustPursue",
            >= 50 => "ShouldPursue",
            >= 30 => "Consider",
            _ => "Skip"
        };

        return new PursuitPriorityDto
        {
            NoticeId = noticeId,
            PursuitScore = pursuitScore,
            Category = category,
            PWinScore = pwinScore,
            PWinConfidence = pwinConfidence,
            OqScore = oqScore,
            OqConfidence = oqConfidence,
            ConfidenceDiscountApplied = discountApplied,
            Quadrant = quadrant
        };
    }
}
