using FedProspector.Core.DTOs.Intelligence;
using FedProspector.Core.Interfaces;
using FedProspector.Infrastructure.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;

namespace FedProspector.Infrastructure.Services;

public class MarketIntelService : IMarketIntelService
{
    private readonly FedProspectorDbContext _context;
    private readonly ILogger<MarketIntelService> _logger;

    public MarketIntelService(FedProspectorDbContext context, ILogger<MarketIntelService> logger)
    {
        _context = context;
        _logger = logger;
    }

    public async Task<MarketShareAnalysisDto> GetMarketShareAsync(string naicsCode, int years = 3, int limit = 10)
    {
        var cutoff = DateOnly.FromDateTime(DateTime.UtcNow.AddYears(-years));

        // Get NAICS description
        var naicsDesc = await _context.RefNaicsCodes
            .AsNoTracking()
            .Where(n => n.NaicsCode == naicsCode)
            .Select(n => n.Description)
            .FirstOrDefaultAsync();

        // Base awards only (modification_number = '0'), within date range
        var baseAwards = _context.FpdsContracts
            .AsNoTracking()
            .Where(c => c.NaicsCode == naicsCode
                        && c.ModificationNumber == "0"
                        && c.DateSigned != null
                        && c.DateSigned >= cutoff);

        // Aggregate stats
        var totalContracts = await baseAwards.CountAsync();
        var totalValue = await baseAwards.SumAsync(c => c.BaseAndAllOptions ?? 0m);
        var averageValue = totalContracts > 0 ? totalValue / totalContracts : 0m;

        // Vendor grouping
        var vendorGroups = await baseAwards
            .Where(c => c.VendorUei != null)
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

        var topVendors = vendorGroups.Select(v => new VendorShareDto
        {
            VendorUei = v.VendorUei,
            VendorName = v.VendorName,
            ContractCount = v.ContractCount,
            TotalValue = v.TotalValue,
            MarketSharePercent = totalValue > 0 ? Math.Round(v.TotalValue / totalValue * 100, 2) : 0m
        }).ToList();

        return new MarketShareAnalysisDto
        {
            NaicsCode = naicsCode,
            NaicsDescription = naicsDesc,
            YearsAnalyzed = years,
            TotalContracts = totalContracts,
            TotalValue = totalValue,
            AverageAwardValue = Math.Round(averageValue, 2),
            TopVendors = topVendors
        };
    }

    public async Task<IncumbentAnalysisDto> GetIncumbentAnalysisAsync(string noticeId)
    {
        var result = new IncumbentAnalysisDto { NoticeId = noticeId };

        // 1. Fetch the opportunity
        var opportunity = await _context.Opportunities
            .AsNoTracking()
            .FirstOrDefaultAsync(o => o.NoticeId == noticeId);

        if (opportunity == null)
        {
            _logger.LogWarning("Opportunity {NoticeId} not found for incumbent analysis", noticeId);
            return result;
        }

        // 2. Find linked contracts via solicitation_number (base awards only)
        var linkedContracts = new List<Core.Models.FpdsContract>();
        if (!string.IsNullOrWhiteSpace(opportunity.SolicitationNumber))
        {
            linkedContracts = await _context.FpdsContracts
                .AsNoTracking()
                .Where(c => c.SolicitationNumber == opportunity.SolicitationNumber
                            && c.ModificationNumber == "0")
                .OrderByDescending(c => c.DateSigned)
                .ToListAsync();
        }

        if (linkedContracts.Count == 0)
        {
            // Fallback: find likely competitors via agency + NAICS + PSC
            var agencyCode = ExtractAgencyCode(opportunity.FullParentPathCode);
            if (!string.IsNullOrWhiteSpace(agencyCode) && !string.IsNullOrWhiteSpace(opportunity.NaicsCode))
            {
                var fiveYearsAgo = DateOnly.FromDateTime(DateTime.UtcNow.AddYears(-5));
                var fallbackQuery = _context.FpdsContracts.AsNoTracking()
                    .Where(c => c.AgencyId == agencyCode
                                && c.NaicsCode == opportunity.NaicsCode
                                && c.ModificationNumber == "0"
                                && c.DateSigned != null
                                && c.DateSigned >= fiveYearsAgo
                                && c.VendorUei != null);

                if (!string.IsNullOrWhiteSpace(opportunity.ClassificationCode))
                    fallbackQuery = fallbackQuery.Where(c => c.PscCode == opportunity.ClassificationCode);

                var likelyCompetitors = await fallbackQuery
                    .GroupBy(c => new { c.VendorUei, c.VendorName })
                    .Select(g => new LikelyCompetitorDto
                    {
                        UeiSam = g.Key.VendorUei,
                        VendorName = g.Key.VendorName ?? "",
                        ContractCount = g.Count(),
                        TotalValue = g.Sum(c => c.BaseAndAllOptions ?? 0m)
                    })
                    .OrderByDescending(v => v.TotalValue)
                    .Take(10)
                    .ToListAsync();

                result.LikelyCompetitors = likelyCompetitors;
                result.IsLikelyIncumbent = false;
            }

            return result;
        }

        result.IsLikelyIncumbent = true;

        // 3. Most recent contract's vendor is the incumbent
        var incumbentContract = linkedContracts[0];
        result.HasIncumbent = true;
        result.IncumbentUei = incumbentContract.VendorUei;
        result.IncumbentName = incumbentContract.VendorName;
        result.ContractId = incumbentContract.ContractId;
        result.ContractValue = incumbentContract.BaseAndAllOptions;
        result.DollarsObligated = incumbentContract.DollarsObligated;

        if (incumbentContract.EffectiveDate.HasValue)
            result.PeriodStart = incumbentContract.EffectiveDate.Value.ToDateTime(TimeOnly.MinValue);

        var endDate = incumbentContract.UltimateCompletionDate ?? incumbentContract.CompletionDate;
        if (endDate.HasValue)
        {
            result.PeriodEnd = endDate.Value.ToDateTime(TimeOnly.MinValue);
            var remaining = (endDate.Value.ToDateTime(TimeOnly.MinValue) - DateTime.UtcNow).Days / 30.0;
            result.MonthsRemaining = Math.Max(0, (int)Math.Ceiling(remaining));
        }

        // 4. Calculate burn rate and percent spent
        if (incumbentContract.DollarsObligated.HasValue && incumbentContract.EffectiveDate.HasValue)
        {
            var monthsElapsed = (DateTime.UtcNow - incumbentContract.EffectiveDate.Value.ToDateTime(TimeOnly.MinValue)).Days / 30.0;
            if (monthsElapsed > 0)
            {
                result.MonthlyBurnRate = Math.Round(incumbentContract.DollarsObligated.Value / (decimal)monthsElapsed, 2);
            }
        }

        if (incumbentContract.DollarsObligated.HasValue && incumbentContract.BaseAndAllOptions.HasValue
            && incumbentContract.BaseAndAllOptions.Value > 0)
        {
            result.PercentSpent = Math.Round(
                incumbentContract.DollarsObligated.Value / incumbentContract.BaseAndAllOptions.Value * 100, 2);
        }

        // 5. Entity registration status
        if (!string.IsNullOrWhiteSpace(incumbentContract.VendorUei))
        {
            var entity = await _context.Entities
                .AsNoTracking()
                .FirstOrDefaultAsync(e => e.UeiSam == incumbentContract.VendorUei);

            if (entity != null)
            {
                result.RegistrationStatus = entity.RegistrationStatus;
                if (entity.RegistrationExpirationDate.HasValue)
                    result.RegistrationExpiration = entity.RegistrationExpirationDate.Value.ToDateTime(TimeOnly.MinValue);

                // Vulnerability: registration status
                if (entity.RegistrationStatus != "A")
                {
                    result.VulnerabilitySignals.Add("SAM registration status is not Active");
                }

                // Vulnerability: registration expiring soon
                if (entity.RegistrationExpirationDate.HasValue)
                {
                    var daysUntilExpiry = (entity.RegistrationExpirationDate.Value.ToDateTime(TimeOnly.MinValue) - DateTime.UtcNow).TotalDays;
                    if (daysUntilExpiry < 0)
                        result.VulnerabilitySignals.Add("SAM registration has expired");
                    else if (daysUntilExpiry <= 90)
                        result.VulnerabilitySignals.Add($"SAM registration expires within {(int)daysUntilExpiry} days");
                }
            }

            // 6. Check exclusions
            var exclusion = await _context.SamExclusions
                .AsNoTracking()
                .Where(e => e.Uei == incumbentContract.VendorUei
                            && (e.TerminationDate == null || e.TerminationDate >= DateOnly.FromDateTime(DateTime.UtcNow)))
                .OrderByDescending(e => e.ActivationDate)
                .FirstOrDefaultAsync();

            if (exclusion != null)
            {
                result.IsExcluded = true;
                result.ExclusionType = exclusion.ExclusionType;
                result.VulnerabilitySignals.Add($"Incumbent is excluded/debarred ({exclusion.ExclusionType})");
            }

            // 7. Count incumbent's contracts in this NAICS
            if (!string.IsNullOrWhiteSpace(opportunity.NaicsCode))
            {
                result.TotalContractsInNaics = await _context.FpdsContracts
                    .AsNoTracking()
                    .CountAsync(c => c.VendorUei == incumbentContract.VendorUei
                                     && c.NaicsCode == opportunity.NaicsCode
                                     && c.ModificationNumber == "0");
            }

            // 8. Consecutive wins — count contracts with same solicitation number
            result.ConsecutiveWins = linkedContracts.Count(c => c.VendorUei == incumbentContract.VendorUei);
        }

        // 9. Spending vulnerability signals
        if (result.PercentSpent.HasValue && incumbentContract.EffectiveDate.HasValue && endDate.HasValue)
        {
            var totalDuration = (endDate.Value.ToDateTime(TimeOnly.MinValue) - incumbentContract.EffectiveDate.Value.ToDateTime(TimeOnly.MinValue)).TotalDays;
            var elapsed = (DateTime.UtcNow - incumbentContract.EffectiveDate.Value.ToDateTime(TimeOnly.MinValue)).TotalDays;

            if (totalDuration > 0 && elapsed > 0)
            {
                var expectedPercent = (decimal)(elapsed / totalDuration) * 100;

                if (result.PercentSpent > expectedPercent * 1.2m)
                    result.VulnerabilitySignals.Add("Over-spending relative to contract timeline");
                else if (result.PercentSpent < expectedPercent * 0.5m)
                    result.VulnerabilitySignals.Add("Significantly under-spending relative to contract timeline");
            }
        }

        return result;
    }

    public async Task<CompetitiveLandscapeDto?> GetCompetitiveLandscapeAsync(string noticeId)
    {
        // 1. Fetch the opportunity
        var opportunity = await _context.Opportunities
            .AsNoTracking()
            .FirstOrDefaultAsync(o => o.NoticeId == noticeId);

        if (opportunity == null)
        {
            _logger.LogWarning("Opportunity {NoticeId} not found for competitive landscape", noticeId);
            return null;
        }

        if (string.IsNullOrWhiteSpace(opportunity.NaicsCode))
        {
            _logger.LogWarning("Opportunity {NoticeId} has no NAICS code for competitive landscape", noticeId);
            return null;
        }

        // 2. Extract agency code from FullParentPathCode (dot-delimited hierarchy like "100.7000")
        var agencyCode = ExtractAgencyCode(opportunity.FullParentPathCode);
        var fiveYearsAgo = DateOnly.FromDateTime(DateTime.UtcNow.AddYears(-5));

        // 3. Query fpds_contract scoped by agency + NAICS for last 5 years
        string? fallbackScope = null;
        var baseQuery = _context.FpdsContracts.AsNoTracking()
            .Where(c => c.NaicsCode == opportunity.NaicsCode
                        && c.ModificationNumber == "0"
                        && c.DateSigned != null
                        && c.DateSigned >= fiveYearsAgo);

        var agencyScopedQuery = !string.IsNullOrWhiteSpace(agencyCode)
            ? baseQuery.Where(c => c.AgencyId == agencyCode)
            : baseQuery;

        // Check distinct vendor count for agency-scoped query
        var agencyDistinctVendors = !string.IsNullOrWhiteSpace(agencyCode)
            ? await agencyScopedQuery.Where(c => c.VendorUei != null).Select(c => c.VendorUei).Distinct().CountAsync()
            : 0;

        // 4. Fallback: if agency-scoped results have < 3 distinct vendors, fall back to NAICS-only
        IQueryable<Core.Models.FpdsContract> activeQuery;
        if (agencyDistinctVendors >= 3)
        {
            activeQuery = agencyScopedQuery;
        }
        else
        {
            activeQuery = baseQuery;
            fallbackScope = "NAICS";
        }

        // Aggregate stats
        var totalContracts = await activeQuery.CountAsync();
        var totalValue = await activeQuery.SumAsync(c => c.BaseAndAllOptions ?? 0m);
        var averageValue = totalContracts > 0 ? totalValue / totalContracts : 0m;

        // Agency-specific average (always computed if agency code exists, even in fallback mode)
        decimal agencyAverageValue = 0m;
        if (!string.IsNullOrWhiteSpace(agencyCode))
        {
            var agencyContracts = await agencyScopedQuery.CountAsync();
            var agencyTotal = await agencyScopedQuery.SumAsync(c => c.BaseAndAllOptions ?? 0m);
            agencyAverageValue = agencyContracts > 0 ? Math.Round(agencyTotal / agencyContracts, 2) : 0m;
        }

        // Distinct vendor count
        var distinctVendorCount = await activeQuery
            .Where(c => c.VendorUei != null)
            .Select(c => c.VendorUei)
            .Distinct()
            .CountAsync();

        // Top 10 vendors by total value
        var vendorGroups = await activeQuery
            .Where(c => c.VendorUei != null)
            .GroupBy(c => new { c.VendorUei, c.VendorName })
            .Select(g => new
            {
                g.Key.VendorUei,
                g.Key.VendorName,
                ContractCount = g.Count(),
                TotalValue = g.Sum(c => c.BaseAndAllOptions ?? 0m)
            })
            .OrderByDescending(v => v.TotalValue)
            .Take(10)
            .ToListAsync();

        var topVendors = vendorGroups.Select(v => new VendorShareDto
        {
            VendorUei = v.VendorUei,
            VendorName = v.VendorName,
            ContractCount = v.ContractCount,
            TotalValue = v.TotalValue,
            MarketSharePercent = totalValue > 0 ? Math.Round(v.TotalValue / totalValue * 100, 2) : 0m
        }).ToList();

        // 5. Competition level (same thresholds as PWinService.ScoreCompetitionLevelAsync)
        var competitionLevel = distinctVendorCount switch
        {
            0 => "Unknown",
            <= 3 => "Low",
            <= 6 => "Moderate",
            <= 10 => "High",
            _ => "Very High"
        };

        return new CompetitiveLandscapeDto
        {
            NaicsCode = opportunity.NaicsCode,
            AgencyCode = agencyCode ?? "",
            SetAsideCode = opportunity.SetAsideCode,
            TotalContracts = totalContracts,
            TotalValue = totalValue,
            AverageAwardValue = Math.Round(averageValue, 2),
            AgencyAverageAwardValue = agencyAverageValue,
            TopVendors = topVendors,
            CompetitionLevel = competitionLevel,
            DistinctVendorCount = distinctVendorCount,
            FallbackScope = fallbackScope
        };
    }

    public async Task<SetAsideShiftDto?> GetSetAsideShiftAsync(string noticeId)
    {
        var row = await _context.SetAsideShifts
            .AsNoTracking()
            .FirstOrDefaultAsync(s => s.NoticeId == noticeId);

        if (row == null)
            return null;

        return new SetAsideShiftDto
        {
            NoticeId = row.NoticeId,
            SolicitationNumber = row.SolicitationNumber,
            CurrentSetAsideCode = row.CurrentSetAsideCode,
            CurrentSetAsideDescription = row.CurrentSetAsideDescription,
            PredecessorSetAsideType = row.PredecessorSetAsideType,
            PredecessorVendorName = row.PredecessorVendorName,
            PredecessorVendorUei = row.PredecessorVendorUei,
            PredecessorDateSigned = row.PredecessorDateSigned?.ToDateTime(TimeOnly.MinValue),
            PredecessorValue = row.PredecessorValue,
            ShiftDetected = row.ShiftDetected
        };
    }

    public async Task<List<SetAsideTrendDto>> GetSetAsideTrendsAsync(string naicsCode)
    {
        var rows = await _context.SetAsideTrends
            .AsNoTracking()
            .Where(t => t.NaicsCode == naicsCode)
            .OrderBy(t => t.FiscalYear)
            .ThenByDescending(t => t.ContractCount)
            .ToListAsync();

        return rows.Select(r => new SetAsideTrendDto
        {
            NaicsCode = r.NaicsCode,
            FiscalYear = r.FiscalYear,
            SetAsideType = r.SetAsideType,
            SetAsideCategory = r.SetAsideCategory,
            ContractCount = r.ContractCount,
            TotalValue = r.TotalValue,
            AvgValue = r.AvgValue
        }).ToList();
    }

    /// <summary>
    /// Extract the top-level agency code from a dot-delimited FullParentPathCode (e.g., "100.7000" -> "100").
    /// </summary>
    private static string? ExtractAgencyCode(string? fullParentPathCode)
    {
        if (string.IsNullOrWhiteSpace(fullParentPathCode))
            return null;

        var dotIndex = fullParentPathCode.IndexOf('.');
        return dotIndex > 0 ? fullParentPathCode[..dotIndex] : fullParentPathCode.Trim();
    }
}
