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

        if (orgNaics.Count == 0 && request.OnlyMyNaics && string.IsNullOrWhiteSpace(request.NaicsCode))
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

        // 4. Filter by NAICS — use specific naicsCode if provided, org's codes if OnlyMyNaics, or skip
        if (!string.IsNullOrWhiteSpace(request.NaicsCode))
        {
            query = query.Where(c => c.NaicsCode == request.NaicsCode);
        }
        else if (request.OnlyMyNaics)
        {
            query = query.Where(c => c.NaicsCode != null && orgNaics.Contains(c.NaicsCode));
        }

        // 5. Filter by set-aside type if provided
        if (!string.IsNullOrWhiteSpace(request.SetAsideType))
        {
            query = query.Where(c => c.SetAsideType == request.SetAsideType);
        }

        // 5b. Filter by agency if provided
        if (!string.IsNullOrWhiteSpace(request.Agency))
        {
            query = query.Where(c => c.AgencyName != null && c.AgencyName.Contains(request.Agency));
        }

        // 5c. Filter by PIID if provided
        if (!string.IsNullOrWhiteSpace(request.Piid))
        {
            query = query.Where(c => c.ContractId.Contains(request.Piid));
        }

        // 5d. Filter by vendor name if provided
        if (!string.IsNullOrWhiteSpace(request.VendorName))
        {
            query = query.Where(c => c.VendorName != null && c.VendorName.Contains(request.VendorName));
        }

        // 6. Query USASpending contracts expiring in the window
        var usaQuery = _context.UsaspendingAwards.AsNoTracking()
            .Where(u => u.AwardType != null && new[] { "DELIVERY ORDER", "PURCHASE ORDER", "BPA CALL", "DEFINITIVE CONTRACT", "DO", "DCA", "PO", "BPA" }.Contains(u.AwardType))
            .Where(u => u.EndDate != null && u.EndDate >= now && u.EndDate <= cutoff);

        if (!string.IsNullOrWhiteSpace(request.NaicsCode))
        {
            usaQuery = usaQuery.Where(u => u.NaicsCode == request.NaicsCode);
        }
        else if (request.OnlyMyNaics)
        {
            usaQuery = usaQuery.Where(u => u.NaicsCode != null && orgNaics.Contains(u.NaicsCode));
        }

        if (!string.IsNullOrWhiteSpace(request.SetAsideType))
        {
            usaQuery = usaQuery.Where(u => u.TypeOfSetAside == request.SetAsideType);
        }

        if (!string.IsNullOrWhiteSpace(request.Agency))
        {
            usaQuery = usaQuery.Where(u => u.AwardingAgencyName != null && u.AwardingAgencyName.Contains(request.Agency));
        }

        if (!string.IsNullOrWhiteSpace(request.Piid))
        {
            usaQuery = usaQuery.Where(u => (u.Piid != null && u.Piid.Contains(request.Piid)) || (u.GeneratedUniqueAwardId != null && u.GeneratedUniqueAwardId.Contains(request.Piid)));
        }

        if (!string.IsNullOrWhiteSpace(request.VendorName))
        {
            usaQuery = usaQuery.Where(u => u.RecipientName != null && u.RecipientName.Contains(request.VendorName));
        }

        // 7. Execute both queries (no joins — entity lookup deferred to after pagination)
        var fpdsResults = await query
            .OrderBy(c => c.UltimateCompletionDate)
            .ToListAsync();

        var usaResults = await usaQuery
            .OrderBy(u => u.EndDate)
            .Take(request.Offset + request.Limit + 50) // ceiling: only fetch what we might need
            .ToListAsync();

        // Build solicitation number lookup for re-solicitation enrichment
        var solicitationByPiid = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (var c in fpdsResults)
        {
            if (!string.IsNullOrWhiteSpace(c.SolicitationNumber))
                solicitationByPiid[c.ContractId] = c.SolicitationNumber;
        }
        foreach (var u in usaResults)
        {
            var piid = u.Piid ?? u.GeneratedUniqueAwardId;
            if (!solicitationByPiid.ContainsKey(piid) && !string.IsNullOrWhiteSpace(u.SolicitationIdentifier))
                solicitationByPiid[piid] = u.SolicitationIdentifier;
        }

        // 8. Map both to DTOs, then dedup by PIID (FPDS preferred)
        var utcNow = DateTime.UtcNow;

        var fpdsDtos = fpdsResults.Select(c => new ExpiringContractDto
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
            MonthlyBurnRate = CalculateMonthlyBurnRate(c.DateSigned, c.DollarsObligated),
            PercentSpent = c.BaseAndAllOptions > 0 && c.DollarsObligated.HasValue
                ? Math.Round(c.DollarsObligated.Value / c.BaseAndAllOptions.Value * 100m, 1)
                : null,
            Source = "FPDS",
            FhOrgId = c.FhOrgId
        }).ToList();

        var usaDtos = usaResults.Select(u => new ExpiringContractDto
        {
            Piid = u.Piid ?? u.GeneratedUniqueAwardId,
            Description = u.AwardDescription,
            NaicsCode = u.NaicsCode,
            SetAsideType = u.TypeOfSetAside,
            VendorUei = u.RecipientUei,
            VendorName = u.RecipientName,
            AgencyName = u.AwardingAgencyName,
            OfficeName = u.AwardingSubAgencyName,
            ContractValue = u.BaseAndAllOptionsValue,
            DollarsObligated = u.TotalObligation,
            CompletionDate = u.EndDate?.ToDateTime(TimeOnly.MinValue),
            DateSigned = u.StartDate?.ToDateTime(TimeOnly.MinValue),
            MonthsRemaining = u.EndDate.HasValue
                ? (u.EndDate.Value.Year - now.Year) * 12
                  + (u.EndDate.Value.Month - now.Month)
                : null,
            MonthlyBurnRate = CalculateMonthlyBurnRate(u.StartDate, u.TotalObligation),
            PercentSpent = u.BaseAndAllOptionsValue > 0 && u.TotalObligation.HasValue
                ? Math.Round(u.TotalObligation.Value / u.BaseAndAllOptionsValue.Value * 100m, 1)
                : null,
            Source = "USASpending",
            FhOrgId = u.FhOrgId
        }).ToList();

        // Dedup: FPDS wins when same PIID exists in both
        var fpdsPiids = new HashSet<string>(fpdsDtos.Select(d => d.Piid), StringComparer.OrdinalIgnoreCase);
        var merged = fpdsDtos
            .Concat(usaDtos.Where(d => !fpdsPiids.Contains(d.Piid)))
            .OrderBy(d => d.CompletionDate)
            .ToList();

        _logger.LogInformation("Expiring contracts: {FpdsCount} FPDS + {UsaCount} USASpending = {MergedCount} merged (after dedup)",
            fpdsDtos.Count, usaDtos.Count, merged.Count);

        // Apply offset/limit to merged set
        var results = merged
            .Skip(request.Offset)
            .Take(request.Limit)
            .ToList();

        // Batch-fetch entity data for just the page results
        var pageUeis = results
            .Select(d => d.VendorUei)
            .Where(u => !string.IsNullOrEmpty(u))
            .Distinct()
            .ToList();

        var entityByUei = pageUeis.Count > 0
            ? await _context.Entities.AsNoTracking()
                .Where(e => pageUeis.Contains(e.UeiSam))
                .ToDictionaryAsync(e => e.UeiSam)
            : new Dictionary<string, Core.Models.Entity>();

        // Enrich with entity data
        foreach (var dto in results)
        {
            if (dto.VendorUei != null && entityByUei.TryGetValue(dto.VendorUei, out var entity))
            {
                dto.RegistrationStatus = entity.RegistrationStatus;
                dto.RegistrationExpiration = entity.RegistrationExpirationDate?.ToDateTime(TimeOnly.MinValue);
            }
        }

        // 9. Re-solicitation matching
        var resultPiids = results.Select(r => r.Piid).ToList();
        var solicitationNumbers = resultPiids
            .Where(p => solicitationByPiid.ContainsKey(p))
            .Select(p => solicitationByPiid[p])
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

        // 9b. Fetch set-aside shift data for matching opportunities
        var matchingNoticeIds = matchingOpportunities.Select(o => o.NoticeId).Distinct().ToList();
        var shiftByNoticeId = matchingNoticeIds.Count > 0
            ? await _context.SetAsideShifts.AsNoTracking()
                .Where(s => matchingNoticeIds.Contains(s.NoticeId))
                .ToDictionaryAsync(s => s.NoticeId)
            : new Dictionary<string, Core.Models.Views.SetAsideShiftView>();

        // 10. Enrich DTOs with re-solicitation and set-aside shift data
        foreach (var dto in results)
        {
            if (solicitationByPiid.TryGetValue(dto.Piid, out var solNum)
                && opportunityBySolicitation.TryGetValue(solNum, out var opp))
            {
                dto.ResolicitationNoticeId = opp.NoticeId;
                dto.ResolicitationStatus = opp.ResponseDeadline.HasValue && opp.ResponseDeadline > utcNow
                    ? "Solicitation Active"
                    : "Pre-Solicitation Posted";

                if (shiftByNoticeId.TryGetValue(opp.NoticeId, out var shift))
                {
                    dto.PredecessorSetAsideType = shift.PredecessorSetAsideType;
                    dto.ShiftDetected = shift.ShiftDetected;
                }
            }
        }

        return results;
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
