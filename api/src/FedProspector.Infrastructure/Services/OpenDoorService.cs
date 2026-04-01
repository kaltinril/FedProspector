using FedProspector.Core.DTOs.Intelligence;
using FedProspector.Core.Interfaces;
using FedProspector.Infrastructure.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;

namespace FedProspector.Infrastructure.Services;

public class OpenDoorService : IOpenDoorService
{
    private readonly FedProspectorDbContext _context;
    private readonly ILogger<OpenDoorService> _logger;

    /// <summary>
    /// Business type codes indicating small business status.
    /// </summary>
    private static readonly HashSet<string> SmallBizCodes = new(StringComparer.OrdinalIgnoreCase)
        { "2X", "8W", "A2", "23", "27", "A4", "QF", "A5", "XX" };

    public OpenDoorService(FedProspectorDbContext context, ILogger<OpenDoorService> logger)
    {
        _context = context;
        _logger = logger;
    }

    public async Task<OpenDoorScoreDto> ScorePrimeAsync(string primeUei, int years = 3)
    {
        var cutoff = DateOnly.FromDateTime(DateTime.UtcNow.AddYears(-years));

        // Get all subawards for this prime in the time window
        var subawards = await _context.SamSubawards.AsNoTracking()
            .Where(s => s.PrimeUei == primeUei && s.SubDate != null && s.SubDate >= cutoff)
            .ToListAsync();

        var primeName = await _context.Entities.AsNoTracking()
            .Where(e => e.UeiSam == primeUei)
            .Select(e => e.LegalBusinessName)
            .FirstOrDefaultAsync() ?? primeUei;

        return await ScorePrimeInternalAsync(primeUei, primeName, subawards, years);
    }

    public async Task<OpenDoorAnalysisDto> FindOpenDoorPrimesAsync(string naicsCode, int years = 3, int limit = 10)
    {
        var cutoff = DateOnly.FromDateTime(DateTime.UtcNow.AddYears(-years));

        // Find primes with subawards in this NAICS
        var primeUeis = await _context.SamSubawards.AsNoTracking()
            .Where(s => s.NaicsCode == naicsCode && s.PrimeUei != null && s.SubDate != null && s.SubDate >= cutoff)
            .Select(s => s.PrimeUei!)
            .Distinct()
            .Take(100)
            .ToListAsync();

        _logger.LogInformation("Found {Count} primes with subawards in NAICS {Naics}", primeUeis.Count, naicsCode);

        var scored = new List<OpenDoorScoreDto>();

        foreach (var primeUei in primeUeis)
        {
            try
            {
                var subawards = await _context.SamSubawards.AsNoTracking()
                    .Where(s => s.PrimeUei == primeUei && s.SubDate != null && s.SubDate >= cutoff)
                    .ToListAsync();

                var primeName = await _context.Entities.AsNoTracking()
                    .Where(e => e.UeiSam == primeUei)
                    .Select(e => e.LegalBusinessName)
                    .FirstOrDefaultAsync() ?? primeUei;

                var score = await ScorePrimeInternalAsync(primeUei, primeName, subawards, years);
                scored.Add(score);
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "Failed to score prime {Uei}", primeUei);
            }
        }

        var topPrimes = scored
            .OrderByDescending(p => p.OpenDoorScore)
            .Take(limit)
            .ToList();

        return new OpenDoorAnalysisDto
        {
            NaicsCode = naicsCode,
            YearsAnalyzed = years,
            TotalPrimesFound = primeUeis.Count,
            Primes = topPrimes
        };
    }

    private async Task<OpenDoorScoreDto> ScorePrimeInternalAsync(
        string primeUei, string primeName, List<Core.Models.SamSubaward> subawards, int years)
    {
        var factors = new List<OpenDoorFactorDto>();

        // 1. Small Business Sub Spend % (weight 0.25)
        var sbSpendFactor = await ScoreSmallBizSpendAsync(subawards);
        factors.Add(sbSpendFactor);

        // 2. Sub Diversity Count (weight 0.15)
        var diversityFactor = ScoreSubDiversity(subawards);
        factors.Add(diversityFactor);

        // 3. Average Subaward Size (weight 0.15)
        var avgSizeFactor = ScoreAverageSubSize(subawards);
        factors.Add(avgSizeFactor);

        // 4. Sub Retention Rate (weight 0.15)
        var retentionFactor = ScoreSubRetention(subawards);
        factors.Add(retentionFactor);

        // 5. NAICS Breadth (weight 0.15)
        var naicsBreadthFactor = ScoreNaicsBreadth(subawards);
        factors.Add(naicsBreadthFactor);

        // 6. Year-over-Year Trend (weight 0.15)
        var trendFactor = ScoreYoyTrend(subawards);
        factors.Add(trendFactor);

        var totalScore = (int)Math.Round(factors.Sum(f => f.WeightedScore));
        totalScore = Math.Clamp(totalScore, 0, 100);

        var realDataCount = factors.Count(f => f.HadRealData);
        var confidence = realDataCount >= 5 ? "High" : realDataCount >= 3 ? "Medium" : "Low";
        var dataCompleteness = (int)Math.Round(realDataCount * 100.0 / factors.Count);

        var category = totalScore switch
        {
            >= 80 => "Champion",
            >= 60 => "Engaged",
            >= 40 => "Minimal",
            _ => "Closed"
        };

        var distinctSubs = subawards.Where(s => s.SubUei != null).Select(s => s.SubUei).Distinct().Count();
        var totalSubValue = subawards.Sum(s => s.SubAmount ?? 0m);

        return new OpenDoorScoreDto
        {
            PrimeUei = primeUei,
            PrimeName = primeName,
            OpenDoorScore = totalScore,
            Category = category,
            Confidence = confidence,
            DataCompletenessPercent = dataCompleteness,
            Factors = factors,
            TotalSubawards = subawards.Count,
            DistinctSubs = distinctSubs,
            TotalSubValue = totalSubValue
        };
    }

    private async Task<OpenDoorFactorDto> ScoreSmallBizSpendAsync(List<Core.Models.SamSubaward> subawards)
    {
        const decimal weight = 0.25m;

        if (subawards.Count == 0)
        {
            return MakeFactor("Small Business Sub Spend %", 0, weight, "No subaward data available", false);
        }

        // Get distinct sub UEIs
        var subUeis = subawards
            .Where(s => s.SubUei != null)
            .Select(s => s.SubUei!)
            .Distinct()
            .ToList();

        if (subUeis.Count == 0)
        {
            return MakeFactor("Small Business Sub Spend %", 0, weight, "No sub UEIs in subaward data", false);
        }

        // Find which sub UEIs have small business type codes
        var smallBizUeis = await _context.EntityBusinessTypes.AsNoTracking()
            .Where(b => subUeis.Contains(b.UeiSam) && SmallBizCodes.Contains(b.BusinessTypeCode))
            .Select(b => b.UeiSam)
            .Distinct()
            .ToListAsync();

        var smallBizUeiSet = new HashSet<string>(smallBizUeis, StringComparer.OrdinalIgnoreCase);

        var totalValue = subawards.Sum(s => s.SubAmount ?? 0m);
        var smallBizValue = subawards
            .Where(s => s.SubUei != null && smallBizUeiSet.Contains(s.SubUei))
            .Sum(s => s.SubAmount ?? 0m);

        var pct = totalValue > 0 ? (double)(smallBizValue / totalValue * 100) : 0;

        int score;
        if (pct > 50) score = 100;
        else if (pct >= 30) score = 75;
        else if (pct >= 15) score = 50;
        else if (pct >= 5) score = 30;
        else score = 10;

        return MakeFactor("Small Business Sub Spend %", score, weight,
            $"{pct:F1}% of sub spend (${smallBizValue:N0} of ${totalValue:N0}) goes to small businesses");
    }

    private static OpenDoorFactorDto ScoreSubDiversity(List<Core.Models.SamSubaward> subawards)
    {
        const decimal weight = 0.15m;

        var distinctSubs = subawards.Where(s => s.SubUei != null).Select(s => s.SubUei).Distinct().Count();

        if (distinctSubs == 0)
        {
            return MakeFactor("Sub Diversity Count", 0, weight, "No subaward data", false);
        }

        var score = Math.Clamp(5 * distinctSubs, 10, 100);

        return MakeFactor("Sub Diversity Count", score, weight,
            $"{distinctSubs} distinct subcontractors used");
    }

    private static OpenDoorFactorDto ScoreAverageSubSize(List<Core.Models.SamSubaward> subawards)
    {
        const decimal weight = 0.15m;

        var withAmount = subawards.Where(s => s.SubAmount.HasValue && s.SubAmount.Value > 0).ToList();
        if (withAmount.Count == 0)
        {
            return MakeFactor("Average Subaward Size", 0, weight, "No subaward amounts available", false);
        }

        var avg = withAmount.Average(s => s.SubAmount!.Value);

        // Continuous curve: score = min(100, avg / 1000)
        int score;
        if (avg >= 100_000) score = 100;
        else if (avg >= 50_000) score = 80;
        else if (avg >= 25_000) score = 60;
        else if (avg >= 10_000) score = 40;
        else score = 20;

        return MakeFactor("Average Subaward Size", score, weight,
            $"Average subaward: ${avg:N0}");
    }

    private static OpenDoorFactorDto ScoreSubRetention(List<Core.Models.SamSubaward> subawards)
    {
        const decimal weight = 0.15m;

        var withDates = subawards.Where(s => s.SubUei != null && s.SubDate.HasValue).ToList();
        if (withDates.Count == 0)
        {
            return MakeFactor("Sub Retention Rate", 0, weight, "No dated subaward data", false);
        }

        // Group by sub UEI, count distinct years each sub appears
        var subYears = withDates
            .GroupBy(s => s.SubUei!)
            .ToDictionary(g => g.Key, g => g.Select(s => s.SubDate!.Value.Year).Distinct().Count());

        var totalDistinctSubs = subYears.Count;
        if (totalDistinctSubs == 0)
        {
            return MakeFactor("Sub Retention Rate", 0, weight, "No sub data for retention analysis", false);
        }

        var returningSubs = subYears.Count(kv => kv.Value >= 2);
        var retentionPct = (double)returningSubs / totalDistinctSubs * 100;

        int score;
        if (retentionPct >= 60) score = 100;
        else if (retentionPct >= 40) score = 70;
        else if (retentionPct >= 20) score = 40;
        else score = 20;

        return MakeFactor("Sub Retention Rate", score, weight,
            $"{retentionPct:F0}% retention ({returningSubs} of {totalDistinctSubs} subs returned in multiple years)");
    }

    private static OpenDoorFactorDto ScoreNaicsBreadth(List<Core.Models.SamSubaward> subawards)
    {
        const decimal weight = 0.15m;

        var distinctNaics = subawards
            .Where(s => !string.IsNullOrEmpty(s.NaicsCode))
            .Select(s => s.NaicsCode)
            .Distinct()
            .Count();

        if (distinctNaics == 0)
        {
            return MakeFactor("NAICS Breadth", 0, weight, "No NAICS codes in subaward data", false);
        }

        var score = Math.Clamp(20 * distinctNaics, 10, 100);

        return MakeFactor("NAICS Breadth", score, weight,
            $"Subawards span {distinctNaics} distinct NAICS code(s)");
    }

    private static OpenDoorFactorDto ScoreYoyTrend(List<Core.Models.SamSubaward> subawards)
    {
        const decimal weight = 0.15m;

        var withDates = subawards.Where(s => s.SubDate.HasValue).ToList();
        if (withDates.Count == 0)
        {
            return MakeFactor("Year-over-Year Trend", 0, weight, "No dated subaward data", false);
        }

        var byYear = withDates
            .GroupBy(s => s.SubDate!.Value.Year)
            .OrderByDescending(g => g.Key)
            .Select(g => new { Year = g.Key, Count = g.Count(), Value = g.Sum(s => s.SubAmount ?? 0m) })
            .ToList();

        if (byYear.Count < 2)
        {
            return MakeFactor("Year-over-Year Trend", 50, weight,
                $"Only 1 year of subaward data ({byYear[0].Year}) — trend unavailable", false);
        }

        var recent = byYear[0];
        var prior = byYear[1];

        double growthPct;
        if (prior.Count > 0)
            growthPct = ((double)recent.Count - prior.Count) / prior.Count * 100;
        else
            growthPct = recent.Count > 0 ? 100 : 0;

        int score;
        string detail;

        if (growthPct >= 20)
        {
            score = 100;
            detail = $"Growing: {recent.Count} subawards in {recent.Year} vs {prior.Count} in {prior.Year} (+{growthPct:F0}%)";
        }
        else if (growthPct >= -20)
        {
            score = 60;
            detail = $"Stable: {recent.Count} subawards in {recent.Year} vs {prior.Count} in {prior.Year} ({growthPct:+0;-0}%)";
        }
        else
        {
            score = 20;
            detail = $"Declining: {recent.Count} subawards in {recent.Year} vs {prior.Count} in {prior.Year} ({growthPct:F0}%)";
        }

        return MakeFactor("Year-over-Year Trend", score, weight, detail);
    }

    private static OpenDoorFactorDto MakeFactor(string name, int score, decimal weight, string detail, bool hadRealData = true)
    {
        return new OpenDoorFactorDto
        {
            Name = name,
            Score = score,
            Weight = weight,
            WeightedScore = Math.Round(score * weight, 2),
            Detail = detail,
            HadRealData = hadRealData
        };
    }
}
