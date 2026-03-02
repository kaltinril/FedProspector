using FedProspector.Core.DTOs.Prospects;
using FedProspector.Core.Interfaces;
using FedProspector.Infrastructure.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;

namespace FedProspector.Infrastructure.Services;

public class GoNoGoScoringService : IGoNoGoScoringService
{
    private readonly FedProspectorDbContext _context;
    private readonly ILogger<GoNoGoScoringService> _logger;

    /// <summary>
    /// Set-aside favorability scores. Matches Python ProspectManager.calculate_score() exactly.
    /// Keys are case-insensitive to handle varying data quality.
    /// </summary>
    private static readonly Dictionary<string, int> SetAsideScores = new(StringComparer.OrdinalIgnoreCase)
    {
        ["WOSB"] = 10, ["EDWOSB"] = 10, ["WOSBSS"] = 10, ["EDWOSBSS"] = 10,
        ["8A"] = 8, ["8AN"] = 8,
        ["SBA"] = 5, ["SBP"] = 5,
        ["HZC"] = 5, ["HZS"] = 5,
        ["SDVOSBC"] = 5, ["SDVOSBS"] = 5,
    };

    /// <summary>
    /// WOSB-related business type codes used for NAICS match scoring.
    /// 2X = Woman Owned, 8W = Woman Owned Small Business, A2 = EDWOSB.
    /// </summary>
    private static readonly string[] WosbBusinessTypeCodes = ["2X", "8W", "A2"];

    public GoNoGoScoringService(FedProspectorDbContext context, ILogger<GoNoGoScoringService> logger)
    {
        _context = context;
        _logger = logger;
    }

    public async Task<ScoreBreakdownDto> CalculateScoreAsync(int prospectId)
    {
        // Fetch prospect + opportunity data (mirrors Python JOIN query)
        var data = await _context.Prospects.AsNoTracking()
            .Where(p => p.ProspectId == prospectId)
            .Join(
                _context.Opportunities.AsNoTracking(),
                p => p.NoticeId,
                o => o.NoticeId,
                (p, o) => new
                {
                    p.ProspectId,
                    p.EstimatedValue,
                    o.SetAsideCode,
                    o.NaicsCode,
                    o.ResponseDeadline,
                    o.AwardAmount
                })
            .FirstOrDefaultAsync();

        if (data is null)
            throw new KeyNotFoundException($"Prospect {prospectId} not found or has no linked opportunity");

        // 1. Set-aside favorability (0-10)
        var saCode = (data.SetAsideCode ?? "").Trim();
        var setAsideScore = SetAsideScores.GetValueOrDefault(saCode, 0);
        var setAsideDetail = string.IsNullOrEmpty(saCode)
            ? $"none -> {setAsideScore} pts"
            : $"{saCode} -> {setAsideScore} pts";

        // 2. Time remaining until deadline (0-10)
        // Python uses datetime.now() (local time), but we use UtcNow for consistency.
        // The scoring brackets are identical to the Python implementation.
        int timeScore;
        string timeDetail;
        if (data.ResponseDeadline.HasValue)
        {
            var daysLeft = (data.ResponseDeadline.Value - DateTime.UtcNow).Days;
            if (daysLeft < 0)
                timeScore = 0;
            else if (daysLeft < 7)
                timeScore = 1;
            else if (daysLeft < 14)
                timeScore = 4;
            else if (daysLeft <= 30)
                timeScore = 7;
            else
                timeScore = 10;

            timeDetail = $"{daysLeft} days left -> {timeScore} pts";
        }
        else
        {
            timeScore = 5;
            timeDetail = "No deadline -> 5 pts";
        }

        // 3. NAICS match (0-10)
        // Check if any entity with WOSB business types has this NAICS code
        var naicsCode = data.NaicsCode;
        int naicsScore = 0;
        if (!string.IsNullOrEmpty(naicsCode))
        {
            var matchCount = await _context.EntityNaicsCodes.AsNoTracking()
                .Join(
                    _context.EntityBusinessTypes.AsNoTracking()
                        .Where(ebt => WosbBusinessTypeCodes.Contains(ebt.BusinessTypeCode)),
                    en => en.UeiSam,
                    ebt => ebt.UeiSam,
                    (en, ebt) => en)
                .Where(en => en.NaicsCode == naicsCode)
                .CountAsync();

            if (matchCount > 0)
                naicsScore = 10;
        }

        var naicsLabel = naicsCode ?? "none";
        var naicsMatchText = naicsScore > 0 ? "MATCH" : "no match";
        var naicsDetail = $"NAICS {naicsLabel}: {naicsMatchText} -> {naicsScore} pts";

        // 4. Award value bracket (0-10)
        // Python: uses award_amount first, falls back to estimated_value
        var value = data.AwardAmount ?? data.EstimatedValue;
        int valueScore;
        string valueDetail;
        if (value.HasValue)
        {
            var v = (double)value.Value;
            if (v >= 1_000_000)
                valueScore = 10;
            else if (v >= 500_000)
                valueScore = 8;
            else if (v >= 100_000)
                valueScore = 6;
            else if (v >= 50_000)
                valueScore = 4;
            else
                valueScore = 2;

            valueDetail = $"${value.Value:N0} -> {valueScore} pts";
        }
        else
        {
            valueScore = 3;
            valueDetail = $"Unknown value -> {valueScore} pts";
        }

        // Total score (0-40)
        var total = setAsideScore + timeScore + naicsScore + valueScore;
        const int maxTotal = 40;
        var percentage = Math.Round((decimal)total / maxTotal * 100, 1);

        // Update prospect record (need a tracked entity for SaveChanges)
        var prospect = await _context.Prospects.FindAsync(prospectId);
        if (prospect is not null)
        {
            prospect.GoNoGoScore = total;
            await _context.SaveChangesAsync();
        }

        return new ScoreBreakdownDto
        {
            ProspectId = prospectId,
            TotalScore = total,
            MaxScore = maxTotal,
            Percentage = percentage,
            Breakdown = new ScoreCriteriaBreakdownDto
            {
                SetAside = new ScoreCriterionDto { Score = setAsideScore, Max = 10, Detail = setAsideDetail },
                TimeRemaining = new ScoreCriterionDto { Score = timeScore, Max = 10, Detail = timeDetail },
                NaicsMatch = new ScoreCriterionDto { Score = naicsScore, Max = 10, Detail = naicsDetail },
                AwardValue = new ScoreCriterionDto { Score = valueScore, Max = 10, Detail = valueDetail }
            }
        };
    }
}
