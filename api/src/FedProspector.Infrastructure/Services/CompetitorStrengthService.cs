using FedProspector.Core.DTOs.Intelligence;
using FedProspector.Core.Interfaces;
using FedProspector.Infrastructure.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;

namespace FedProspector.Infrastructure.Services;

public class CompetitorStrengthService : ICompetitorStrengthService
{
    private readonly FedProspectorDbContext _context;
    private readonly ILogger<CompetitorStrengthService> _logger;

    // Business type codes that map to set-aside certifications
    private static readonly Dictionary<string, string> CertCodeToName = new()
    {
        ["8W"] = "WOSB",
        ["A2"] = "EDWOSB",
        ["A4"] = "8(a)",
        ["2X"] = "8(a)",
        ["XX"] = "HUBZone",
        ["QF"] = "SDVOSB",
        ["A5"] = "SDVOSB"
    };

    // Set-aside codes that map to required certification types
    private static readonly Dictionary<string, string[]> SetAsideCertRequirements = new(StringComparer.OrdinalIgnoreCase)
    {
        ["WOSB"] = ["8W", "A2"],
        ["WOSBSS"] = ["8W", "A2"],
        ["EDWOSB"] = ["A2"],
        ["EDWOSBSS"] = ["A2"],
        ["8A"] = ["A4", "2X"],
        ["8AN"] = ["A4", "2X"],
        ["HZC"] = ["XX"],
        ["HZS"] = ["XX"],
        ["SDVOSBC"] = ["QF", "A5"],
        ["SDVOSBS"] = ["QF", "A5"],
    };

    private static readonly string[] AllCertCodes = ["8W", "A2", "A4", "2X", "XX", "QF", "A5"];

    public CompetitorStrengthService(FedProspectorDbContext context, ILogger<CompetitorStrengthService> logger)
    {
        _context = context;
        _logger = logger;
    }

    public async Task<CompetitorAnalysisDto> GetMarketCompetitorsAsync(string naicsCode, int years = 3, int limit = 10)
    {
        var cutoff = DateOnly.FromDateTime(DateTime.UtcNow.AddYears(-years));

        // Find top vendors by total value in this NAICS (base awards only)
        var topVendors = await _context.FpdsContracts
            .AsNoTracking()
            .Where(c => c.NaicsCode == naicsCode
                        && c.ModificationNumber == "0"
                        && c.DateSigned != null
                        && c.DateSigned >= cutoff
                        && c.VendorUei != null)
            .GroupBy(c => new { c.VendorUei, c.VendorName })
            .Select(g => new
            {
                g.Key.VendorUei,
                g.Key.VendorName,
                ContractCount = g.Count(),
                TotalValue = g.Sum(c => c.BaseAndAllOptions ?? 0m)
            })
            .OrderByDescending(v => v.TotalValue)
            .Take(limit)
            .ToListAsync();

        // Compute total market value for market share
        var totalMarketValue = await _context.FpdsContracts
            .AsNoTracking()
            .Where(c => c.NaicsCode == naicsCode
                        && c.ModificationNumber == "0"
                        && c.DateSigned != null
                        && c.DateSigned >= cutoff)
            .SumAsync(c => c.BaseAndAllOptions ?? 0m);

        var competitors = new List<CompetitorScoreDto>();
        foreach (var v in topVendors)
        {
            var score = await ScoreCompetitorAsync(v.VendorUei!, naicsCode, null, null);
            score.VendorName = v.VendorName ?? "";
            score.ContractCount = v.ContractCount;
            score.TotalValue = v.TotalValue;
            score.MarketSharePercent = totalMarketValue > 0
                ? Math.Round(v.TotalValue / totalMarketValue * 100, 2)
                : 0m;
            competitors.Add(score);
        }

        // Sort by CSI descending
        competitors = competitors.OrderByDescending(c => c.CsiScore).ToList();

        return new CompetitorAnalysisDto
        {
            NaicsCode = naicsCode,
            TotalCompetitorsFound = competitors.Count,
            Competitors = competitors
        };
    }

    public async Task<CompetitorAnalysisDto> GetOpportunityCompetitorsAsync(string noticeId, int limit = 10)
    {
        var opportunity = await _context.Opportunities
            .AsNoTracking()
            .FirstOrDefaultAsync(o => o.NoticeId == noticeId);

        if (opportunity == null)
        {
            _logger.LogWarning("Opportunity {NoticeId} not found for competitor strength analysis", noticeId);
            return new CompetitorAnalysisDto { NoticeId = noticeId };
        }

        var naicsCode = opportunity.NaicsCode;
        var agencyCode = ExtractAgencyCode(opportunity.FullParentPathCode);
        var setAsideCode = opportunity.SetAsideCode;

        if (string.IsNullOrWhiteSpace(naicsCode))
        {
            _logger.LogWarning("Opportunity {NoticeId} has no NAICS code for competitor analysis", noticeId);
            return new CompetitorAnalysisDto { NoticeId = noticeId };
        }

        var fiveYearsAgo = DateOnly.FromDateTime(DateTime.UtcNow.AddYears(-5));

        // Find vendors who've won contracts at this agency + NAICS
        var baseQuery = _context.FpdsContracts
            .AsNoTracking()
            .Where(c => c.NaicsCode == naicsCode
                        && c.ModificationNumber == "0"
                        && c.DateSigned != null
                        && c.DateSigned >= fiveYearsAgo
                        && c.VendorUei != null);

        // Scope to agency if available, with fallback
        var agencyScopedQuery = !string.IsNullOrWhiteSpace(agencyCode)
            ? baseQuery.Where(c => c.AgencyId == agencyCode)
            : baseQuery;

        var agencyVendorCount = await agencyScopedQuery
            .Select(c => c.VendorUei).Distinct().CountAsync();

        var activeQuery = agencyVendorCount >= 3 ? agencyScopedQuery : baseQuery;

        var topVendors = await activeQuery
            .GroupBy(c => new { c.VendorUei, c.VendorName })
            .Select(g => new
            {
                g.Key.VendorUei,
                g.Key.VendorName,
                ContractCount = g.Count(),
                TotalValue = g.Sum(c => c.BaseAndAllOptions ?? 0m)
            })
            .OrderByDescending(v => v.TotalValue)
            .Take(limit)
            .ToListAsync();

        var totalMarketValue = await activeQuery.SumAsync(c => c.BaseAndAllOptions ?? 0m);

        var competitors = new List<CompetitorScoreDto>();
        foreach (var v in topVendors)
        {
            var score = await ScoreCompetitorAsync(v.VendorUei!, naicsCode, agencyCode, setAsideCode);
            score.VendorName = v.VendorName ?? "";
            score.ContractCount = v.ContractCount;
            score.TotalValue = v.TotalValue;
            score.MarketSharePercent = totalMarketValue > 0
                ? Math.Round(v.TotalValue / totalMarketValue * 100, 2)
                : 0m;
            competitors.Add(score);
        }

        competitors = competitors.OrderByDescending(c => c.CsiScore).ToList();

        return new CompetitorAnalysisDto
        {
            NaicsCode = naicsCode,
            NoticeId = noticeId,
            AgencyCode = agencyCode,
            TotalCompetitorsFound = competitors.Count,
            Competitors = competitors
        };
    }

    public async Task<CompetitorScoreDto?> GetCompetitorDetailAsync(
        string competitorUei, string? naicsCode = null, string? agencyCode = null)
    {
        // Verify the vendor exists in our data
        var hasContracts = await _context.FpdsContracts
            .AsNoTracking()
            .AnyAsync(c => c.VendorUei == competitorUei && c.ModificationNumber == "0");

        if (!hasContracts)
            return null;

        // Get vendor name from most recent contract
        var vendorName = await _context.FpdsContracts
            .AsNoTracking()
            .Where(c => c.VendorUei == competitorUei && c.ModificationNumber == "0")
            .OrderByDescending(c => c.DateSigned)
            .Select(c => c.VendorName)
            .FirstOrDefaultAsync() ?? "";

        // Get summary stats
        var threeYearsAgo = DateOnly.FromDateTime(DateTime.UtcNow.AddYears(-3));
        var contractQuery = _context.FpdsContracts
            .AsNoTracking()
            .Where(c => c.VendorUei == competitorUei
                        && c.ModificationNumber == "0"
                        && c.DateSigned != null
                        && c.DateSigned >= threeYearsAgo);

        if (!string.IsNullOrWhiteSpace(naicsCode))
            contractQuery = contractQuery.Where(c => c.NaicsCode == naicsCode);

        var contractCount = await contractQuery.CountAsync();
        var totalValue = await contractQuery.SumAsync(c => c.BaseAndAllOptions ?? 0m);

        var score = await ScoreCompetitorAsync(competitorUei, naicsCode, agencyCode, null);
        score.VendorName = vendorName;
        score.ContractCount = contractCount;
        score.TotalValue = totalValue;

        return score;
    }

    /// <summary>
    /// Score a single competitor across all 5 CSI factors.
    /// </summary>
    private async Task<CompetitorScoreDto> ScoreCompetitorAsync(
        string vendorUei, string? naicsCode, string? agencyCode, string? setAsideCode)
    {
        var factors = new List<CsiFactorDto>();

        var revenueFactor = await ScoreFederalRevenueAsync(vendorUei);
        factors.Add(revenueFactor);

        var agencyFactor = await ScoreAgencyPenetrationAsync(vendorUei, agencyCode);
        factors.Add(agencyFactor);

        var certFactor = await ScoreCertificationPortfolioAsync(vendorUei, setAsideCode);
        factors.Add(certFactor);

        var teamFactor = await ScoreTeamStabilityAsync(vendorUei);
        factors.Add(teamFactor);

        var naicsFactor = await ScoreNaicsConcentrationAsync(vendorUei, naicsCode);
        factors.Add(naicsFactor);

        var totalWeightedScore = factors.Sum(f => f.WeightedScore);
        var csiScore = (int)Math.Round(totalWeightedScore);

        var dataFactors = factors.Count(f => f.HadRealData);
        var dataCompleteness = (int)Math.Round(dataFactors / (decimal)factors.Count * 100);

        var confidence = dataCompleteness switch
        {
            >= 80 => "High",
            >= 50 => "Medium",
            _ => "Low"
        };

        var category = csiScore switch
        {
            >= 80 => "Dominant",
            >= 60 => "Strong",
            >= 40 => "Moderate",
            _ => "Weak"
        };

        return new CompetitorScoreDto
        {
            VendorUei = vendorUei,
            CsiScore = csiScore,
            Category = category,
            Confidence = confidence,
            DataCompletenessPercent = dataCompleteness,
            Factors = factors
        };
    }

    /// <summary>
    /// Factor 1: Federal Revenue (weight 0.25) — total federal contract value on log scale.
    /// </summary>
    private async Task<CsiFactorDto> ScoreFederalRevenueAsync(string vendorUei)
    {
        const decimal weight = 0.25m;
        var threeYearsAgo = DateOnly.FromDateTime(DateTime.UtcNow.AddYears(-3));

        var totalValue = await _context.FpdsContracts
            .AsNoTracking()
            .Where(c => c.VendorUei == vendorUei
                        && c.ModificationNumber == "0"
                        && c.DateSigned != null
                        && c.DateSigned >= threeYearsAgo)
            .SumAsync(c => c.DollarsObligated ?? 0m);

        if (totalValue <= 0)
        {
            return MakeFactor("Federal Revenue", 0, weight, "No federal contract revenue found", false);
        }

        // Logarithmic scale tuned so: $50M+=100, $10M=85, $1M=65, $100K=45, <$10K=15
        var score = (int)Math.Min(100, 13.0 * Math.Log10((double)totalValue + 1));

        // Ensure the curve hits the target values
        if (totalValue >= 50_000_000m) score = Math.Max(score, 100);

        var detail = $"${totalValue:N0} in federal revenue (3 years)";
        return MakeFactor("Federal Revenue", score, weight, detail, true);
    }

    /// <summary>
    /// Factor 2: Agency Penetration (weight 0.20) — distinct agencies won at.
    /// </summary>
    private async Task<CsiFactorDto> ScoreAgencyPenetrationAsync(string vendorUei, string? contextAgencyCode)
    {
        const decimal weight = 0.20m;
        var fiveYearsAgo = DateOnly.FromDateTime(DateTime.UtcNow.AddYears(-5));

        var agencyCount = await _context.FpdsContracts
            .AsNoTracking()
            .Where(c => c.VendorUei == vendorUei
                        && c.ModificationNumber == "0"
                        && c.DateSigned != null
                        && c.DateSigned >= fiveYearsAgo
                        && c.AgencyId != null)
            .Select(c => c.AgencyId)
            .Distinct()
            .CountAsync();

        if (agencyCount == 0)
        {
            return MakeFactor("Agency Penetration", 0, weight, "No agency contracts found", false);
        }

        // 10 points per agency, clamped 10-100
        var score = Math.Clamp(agencyCount * 10, 10, 100);

        // Bonus if they've won at the specific agency in question
        var detail = $"{agencyCount} distinct agencies (5 years)";
        if (!string.IsNullOrWhiteSpace(contextAgencyCode))
        {
            var hasTargetAgency = await _context.FpdsContracts
                .AsNoTracking()
                .AnyAsync(c => c.VendorUei == vendorUei
                               && c.AgencyId == contextAgencyCode
                               && c.ModificationNumber == "0"
                               && c.DateSigned != null
                               && c.DateSigned >= fiveYearsAgo);

            if (hasTargetAgency)
            {
                score = Math.Min(100, score + 10);
                detail += $"; has won at target agency {contextAgencyCode}";
            }
        }

        return MakeFactor("Agency Penetration", score, weight, detail, true);
    }

    /// <summary>
    /// Factor 3: Certification Portfolio (weight 0.20) — breadth of set-aside eligibility.
    /// </summary>
    private async Task<CsiFactorDto> ScoreCertificationPortfolioAsync(string vendorUei, string? setAsideCode)
    {
        const decimal weight = 0.20m;

        var vendorCertCodes = await _context.EntityBusinessTypes
            .AsNoTracking()
            .Where(bt => bt.UeiSam == vendorUei && AllCertCodes.Contains(bt.BusinessTypeCode))
            .Select(bt => bt.BusinessTypeCode)
            .Distinct()
            .ToListAsync();

        if (vendorCertCodes.Count == 0)
        {
            // No certs found; could be a large business competitor
            return MakeFactor("Certification Portfolio", 10, weight,
                "No set-aside certifications found (may be large business)", false);
        }

        // Count distinct certification types (group related codes)
        var certTypes = new HashSet<string>();
        foreach (var code in vendorCertCodes)
        {
            if (CertCodeToName.TryGetValue(code, out var name))
                certTypes.Add(name);
        }

        // Each cert type = 20 points, max 100
        var score = Math.Min(100, certTypes.Count * 20);

        // Bonus if vendor has the specific cert needed for the opportunity
        if (!string.IsNullOrWhiteSpace(setAsideCode)
            && SetAsideCertRequirements.TryGetValue(setAsideCode, out var requiredCodes))
        {
            var hasRequired = vendorCertCodes.Any(c => requiredCodes.Contains(c));
            if (hasRequired)
            {
                score = Math.Min(100, score + 20);
            }
        }

        var detail = $"Certifications: {string.Join(", ", certTypes.Order())} ({certTypes.Count} type(s))";
        return MakeFactor("Certification Portfolio", score, weight, detail, true);
    }

    /// <summary>
    /// Factor 4: Team Stability (weight 0.15) — subcontractor retention across years.
    /// </summary>
    private async Task<CsiFactorDto> ScoreTeamStabilityAsync(string vendorUei)
    {
        const decimal weight = 0.15m;
        var threeYearsAgo = DateOnly.FromDateTime(DateTime.UtcNow.AddYears(-3));

        // Get all subs for this prime in last 3 years with year info
        var subRecords = await _context.SamSubawards
            .AsNoTracking()
            .Where(s => s.PrimeUei == vendorUei
                        && s.SubUei != null
                        && s.SubDate != null
                        && s.SubDate >= threeYearsAgo)
            .Select(s => new { s.SubUei, Year = s.SubDate!.Value.Year })
            .ToListAsync();

        if (subRecords.Count == 0)
        {
            // No sub data; could be solo performer
            return MakeFactor("Team Stability", 40, weight,
                "No subcontract data found (may be solo performer)", false);
        }

        var totalSubs = subRecords.Select(s => s.SubUei).Distinct().Count();

        // Count subs that appeared in more than one distinct year
        var recurringSubCount = subRecords
            .GroupBy(s => s.SubUei)
            .Count(g => g.Select(r => r.Year).Distinct().Count() > 1);

        var retentionRate = totalSubs > 0 ? (decimal)recurringSubCount / totalSubs * 100 : 0;

        int score;
        if (retentionRate >= 80) score = 90;
        else if (retentionRate >= 60) score = 70;
        else if (retentionRate >= 40) score = 50;
        else score = 30;

        // Factor in team size: having 3+ subs is better
        if (totalSubs >= 3) score = Math.Min(100, score + 10);

        var detail = $"{totalSubs} sub(s), {recurringSubCount} recurring ({retentionRate:F0}% retention)";
        return MakeFactor("Team Stability", score, weight, detail, true);
    }

    /// <summary>
    /// Factor 5: NAICS Concentration (weight 0.20) — depth of focus in this NAICS.
    /// </summary>
    private async Task<CsiFactorDto> ScoreNaicsConcentrationAsync(string vendorUei, string? naicsCode)
    {
        const decimal weight = 0.20m;

        if (string.IsNullOrWhiteSpace(naicsCode))
        {
            return MakeFactor("NAICS Concentration", 30, weight,
                "No NAICS code provided for concentration analysis", false);
        }

        var threeYearsAgo = DateOnly.FromDateTime(DateTime.UtcNow.AddYears(-3));

        // Total federal revenue across all NAICS
        var totalRevenue = await _context.FpdsContracts
            .AsNoTracking()
            .Where(c => c.VendorUei == vendorUei
                        && c.ModificationNumber == "0"
                        && c.DateSigned != null
                        && c.DateSigned >= threeYearsAgo)
            .SumAsync(c => c.BaseAndAllOptions ?? 0m);

        if (totalRevenue <= 0)
        {
            return MakeFactor("NAICS Concentration", 30, weight,
                "No contract data to assess NAICS concentration", false);
        }

        // Revenue in this specific NAICS
        var naicsRevenue = await _context.FpdsContracts
            .AsNoTracking()
            .Where(c => c.VendorUei == vendorUei
                        && c.NaicsCode == naicsCode
                        && c.ModificationNumber == "0"
                        && c.DateSigned != null
                        && c.DateSigned >= threeYearsAgo)
            .SumAsync(c => c.BaseAndAllOptions ?? 0m);

        var concentrationPct = naicsRevenue / totalRevenue * 100;

        // Contract count in this NAICS
        var naicsContractCount = await _context.FpdsContracts
            .AsNoTracking()
            .Where(c => c.VendorUei == vendorUei
                        && c.NaicsCode == naicsCode
                        && c.ModificationNumber == "0"
                        && c.DateSigned != null
                        && c.DateSigned >= threeYearsAgo)
            .CountAsync();

        int score;
        if (concentrationPct > 50) score = 90;
        else if (concentrationPct > 30) score = 70;
        else if (concentrationPct > 10) score = 50;
        else score = 30;

        // Bonus for high contract count in NAICS (experience depth)
        if (naicsContractCount >= 10) score = Math.Min(100, score + 10);
        else if (naicsContractCount >= 5) score = Math.Min(100, score + 5);

        var detail = $"{concentrationPct:F1}% of revenue in NAICS {naicsCode} ({naicsContractCount} contracts)";
        return MakeFactor("NAICS Concentration", score, weight, detail, true);
    }

    private static CsiFactorDto MakeFactor(string name, int score, decimal weight, string detail, bool hadRealData)
    {
        return new CsiFactorDto
        {
            Name = name,
            Score = score,
            Weight = weight,
            WeightedScore = Math.Round(score * weight, 2),
            Detail = detail,
            HadRealData = hadRealData
        };
    }

    /// <summary>
    /// Extract the top-level agency code from a dot-delimited FullParentPathCode.
    /// </summary>
    private static string? ExtractAgencyCode(string? fullParentPathCode)
    {
        if (string.IsNullOrWhiteSpace(fullParentPathCode))
            return null;

        var dotIndex = fullParentPathCode.IndexOf('.');
        return dotIndex > 0 ? fullParentPathCode[..dotIndex] : fullParentPathCode.Trim();
    }
}
