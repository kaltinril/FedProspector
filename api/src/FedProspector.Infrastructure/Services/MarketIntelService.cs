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
        if (string.IsNullOrWhiteSpace(opportunity.SolicitationNumber))
        {
            return result;
        }

        var linkedContracts = await _context.FpdsContracts
            .AsNoTracking()
            .Where(c => c.SolicitationNumber == opportunity.SolicitationNumber
                        && c.ModificationNumber == "0")
            .OrderByDescending(c => c.DateSigned)
            .ToListAsync();

        if (linkedContracts.Count == 0)
        {
            return result;
        }

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
}
