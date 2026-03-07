using FedProspector.Core.DTOs.Intelligence;
using FedProspector.Core.Interfaces;
using FedProspector.Infrastructure.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;

namespace FedProspector.Infrastructure.Services;

public class ExpiringContractService : IExpiringContractService
{
    private readonly FedProspectorDbContext _context;
    private readonly ILogger<ExpiringContractService> _logger;

    public ExpiringContractService(FedProspectorDbContext context, ILogger<ExpiringContractService> logger)
    {
        _context = context;
        _logger = logger;
    }

    public async Task<List<ExpiringContractDto>> GetExpiringContractsAsync(int orgId, ExpiringContractSearchRequest request)
    {
        // 1. Get the org's NAICS codes
        var orgNaics = await _context.OrganizationNaics
            .AsNoTracking()
            .Where(on => on.OrganizationId == orgId)
            .Select(on => on.NaicsCode)
            .ToListAsync();

        if (orgNaics.Count == 0)
        {
            _logger.LogWarning("Organization {OrgId} has no NAICS codes configured", orgId);
            return [];
        }

        // 2. Build the expiration window
        var now = DateOnly.FromDateTime(DateTime.UtcNow);
        var cutoff = now.AddMonths(request.MonthsAhead);

        // 3. Query base awards expiring within the window
        var query = _context.FpdsContracts.AsNoTracking()
            .Where(c => c.ModificationNumber == "0")
            .Where(c => c.UltimateCompletionDate != null
                && c.UltimateCompletionDate >= now
                && c.UltimateCompletionDate <= cutoff);

        // 4. Filter by NAICS — use specific naicsCode if provided, otherwise org's codes
        if (!string.IsNullOrWhiteSpace(request.NaicsCode))
        {
            query = query.Where(c => c.NaicsCode == request.NaicsCode);
        }
        else
        {
            query = query.Where(c => c.NaicsCode != null && orgNaics.Contains(c.NaicsCode));
        }

        // 5. Filter by set-aside type if provided
        if (!string.IsNullOrWhiteSpace(request.SetAsideType))
        {
            query = query.Where(c => c.SetAsideType == request.SetAsideType);
        }

        // 6. Join entity for incumbent registration status, exclusion for debarment
        var joined = from c in query
            join e in _context.Entities.AsNoTracking()
                on c.VendorUei equals e.UeiSam into entityJoin
            from e in entityJoin.DefaultIfEmpty()
            join ex in _context.SamExclusions.AsNoTracking()
                .Where(x => x.TerminationDate == null)
                on c.VendorUei equals ex.Uei into exclusionJoin
            from ex in exclusionJoin.DefaultIfEmpty()
            select new { Contract = c, Entity = e, Exclusion = ex };

        // 7. Order by completion date ascending (soonest expiring first)
        var ordered = joined.OrderBy(x => x.Contract.UltimateCompletionDate);

        // 8. Apply offset/limit
        var results = await ordered
            .Skip(request.Offset)
            .Take(request.Limit)
            .ToListAsync();

        // 9. Check for re-solicitation: match solicitation_number to opportunity
        var solicitationNumbers = results
            .Where(r => !string.IsNullOrWhiteSpace(r.Contract.SolicitationNumber))
            .Select(r => r.Contract.SolicitationNumber!)
            .Distinct()
            .ToList();

        var matchingOpportunities = solicitationNumbers.Count > 0
            ? await _context.Opportunities.AsNoTracking()
                .Where(o => o.SolicitationNumber != null && solicitationNumbers.Contains(o.SolicitationNumber))
                .Select(o => new
                {
                    o.NoticeId,
                    o.SolicitationNumber,
                    o.ResponseDeadline,
                    o.ArchiveDate
                })
                .ToListAsync()
            : [];

        var opportunityBySolicitation = matchingOpportunities
            .GroupBy(o => o.SolicitationNumber!)
            .ToDictionary(
                g => g.Key,
                g => g.OrderByDescending(o => o.ResponseDeadline).First());

        // 10. Map to DTOs
        var utcNow = DateTime.UtcNow;
        return results.Select(r =>
        {
            var c = r.Contract;
            var dto = new ExpiringContractDto
            {
                Piid = c.ContractId,
                Description = c.Description,
                NaicsCode = c.NaicsCode,
                SetAsideType = c.SetAsideType,
                VendorUei = c.VendorUei,
                VendorName = c.VendorName,
                AgencyName = c.AgencyName,
                OfficeName = c.ContractingOfficeName,
                ContractValue = c.BaseAndAllOptions,
                DollarsObligated = c.DollarsObligated,
                CompletionDate = c.UltimateCompletionDate?.ToDateTime(TimeOnly.MinValue),
                DateSigned = c.DateSigned?.ToDateTime(TimeOnly.MinValue),
                MonthsRemaining = c.UltimateCompletionDate.HasValue
                    ? (c.UltimateCompletionDate.Value.Year - now.Year) * 12
                      + (c.UltimateCompletionDate.Value.Month - now.Month)
                    : null,
                // Incumbent health
                RegistrationStatus = r.Entity?.RegistrationStatus,
                RegistrationExpiration = r.Entity?.RegistrationExpirationDate?.ToDateTime(TimeOnly.MinValue),
                IsExcluded = r.Exclusion != null,
                ExclusionType = r.Exclusion?.ExclusionType,
                // Burn rate
                MonthlyBurnRate = CalculateMonthlyBurnRate(c.DateSigned, c.DollarsObligated),
                PercentSpent = c.BaseAndAllOptions > 0 && c.DollarsObligated.HasValue
                    ? Math.Round(c.DollarsObligated.Value / c.BaseAndAllOptions.Value * 100m, 1)
                    : null
            };

            // Re-solicitation status
            if (!string.IsNullOrWhiteSpace(c.SolicitationNumber)
                && opportunityBySolicitation.TryGetValue(c.SolicitationNumber, out var opp))
            {
                dto.ResolicitationNoticeId = opp.NoticeId;
                dto.ResolicitationStatus = opp.ResponseDeadline.HasValue && opp.ResponseDeadline > utcNow
                    ? "Solicitation Active"
                    : "Pre-Solicitation Posted";
            }

            return dto;
        }).ToList();
    }

    private static decimal? CalculateMonthlyBurnRate(DateOnly? dateSigned, decimal? dollarsObligated)
    {
        if (!dateSigned.HasValue || !dollarsObligated.HasValue)
            return null;

        var now = DateOnly.FromDateTime(DateTime.UtcNow);
        var elapsedMonths = (now.Year - dateSigned.Value.Year) * 12
                          + (now.Month - dateSigned.Value.Month);

        return elapsedMonths > 0
            ? Math.Round(dollarsObligated.Value / elapsedMonths, 2)
            : null;
    }
}
