using FedProspector.Core.DTOs;
using FedProspector.Core.DTOs.Intelligence;
using FedProspector.Core.Interfaces;
using FedProspector.Infrastructure.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;

namespace FedProspector.Infrastructure.Services;

public class CompetitiveIntelService : ICompetitiveIntelService
{
    private readonly FedProspectorDbContext _context;
    private readonly ILogger<CompetitiveIntelService> _logger;

    public CompetitiveIntelService(FedProspectorDbContext context, ILogger<CompetitiveIntelService> logger)
    {
        _context = context;
        _logger = logger;
    }

    public async Task<PagedResponse<RecompeteCandidateDto>> GetRecompeteCandidatesAsync(
        string? naicsCode, string? agencyCode, string? setAsideCode, int page, int pageSize)
    {
        var query = _context.RecompeteCandidates.AsNoTracking();

        if (!string.IsNullOrWhiteSpace(naicsCode))
            query = query.Where(r => r.NaicsCode == naicsCode);

        if (!string.IsNullOrWhiteSpace(agencyCode))
            query = query.Where(r => r.ContractingOfficeId != null &&
                r.ContractingOfficeId.StartsWith(agencyCode));

        if (!string.IsNullOrWhiteSpace(setAsideCode))
            query = query.Where(r => r.SetAsideType == setAsideCode);

        var totalCount = await query.CountAsync();

        var items = await query
            .OrderBy(r => r.DaysUntilEnd)
            .ThenByDescending(r => r.ContractValue)
            .Skip((page - 1) * pageSize)
            .Take(pageSize)
            .ToListAsync();

        var dtos = items.Select(r => new RecompeteCandidateDto
        {
            Piid = r.Piid,
            Source = r.Source,
            Description = r.Description,
            NaicsCode = r.NaicsCode,
            SetAsideType = r.SetAsideType,
            VendorUei = r.VendorUei,
            VendorName = r.VendorName,
            AgencyName = r.AgencyName,
            ContractingOfficeId = r.ContractingOfficeId,
            ContractingOfficeName = r.ContractingOfficeName,
            ContractValue = r.ContractValue,
            DollarsObligated = r.DollarsObligated,
            CurrentEndDate = r.CurrentEndDate,
            DateSigned = r.DateSigned,
            SolicitationNumber = r.SolicitationNumber,
            TypeOfContractPricing = r.TypeOfContractPricing,
            ExtentCompeted = r.ExtentCompeted,
            DaysUntilEnd = r.DaysUntilEnd,
            IncumbentRegistrationStatus = r.IncumbentRegistrationStatus,
            IncumbentRegExpiration = r.IncumbentRegExpiration
        }).ToList();

        return new PagedResponse<RecompeteCandidateDto>
        {
            Items = dtos,
            Page = page,
            PageSize = pageSize,
            TotalCount = totalCount
        };
    }

    public async Task<List<AgencyRecompetePatternDto>> GetAgencyRecompetePatternsAsync(
        string? agencyCode, string? officeCode)
    {
        var query = _context.AgencyRecompetePatterns.AsNoTracking();

        if (!string.IsNullOrWhiteSpace(officeCode))
            query = query.Where(p => p.ContractingOfficeId == officeCode);
        else if (!string.IsNullOrWhiteSpace(agencyCode))
            query = query.Where(p => p.ContractingOfficeId.StartsWith(agencyCode));

        var rows = await query
            .OrderByDescending(p => p.TotalContractsAnalyzed)
            .Take(100)
            .ToListAsync();

        return rows.Select(p => new AgencyRecompetePatternDto
        {
            ContractingOfficeId = p.ContractingOfficeId,
            ContractingOfficeName = p.ContractingOfficeName,
            AgencyName = p.AgencyName,
            IncumbentRetentionRatePct = p.IncumbentRetentionRatePct,
            NewVendorPenetrationPct = p.NewVendorPenetrationPct,
            SetAsideShiftFrequencyPct = p.SetAsideShiftFrequencyPct,
            AvgSolicitationLeadTimeDays = p.AvgSolicitationLeadTimeDays,
            BridgeExtensionFrequencyPct = p.BridgeExtensionFrequencyPct,
            SoleSourceRatePct = p.SoleSourceRatePct,
            NaicsShiftRatePct = p.NaicsShiftRatePct,
            TotalContractsAnalyzed = p.TotalContractsAnalyzed
        }).ToList();
    }

    public async Task<CompetitorDossierDto?> GetCompetitorDossierAsync(string uei)
    {
        var row = await _context.CompetitorDossiers
            .AsNoTracking()
            .FirstOrDefaultAsync(d => d.UeiSam == uei);

        if (row == null)
            return null;

        return new CompetitorDossierDto
        {
            UeiSam = row.UeiSam,
            LegalBusinessName = row.LegalBusinessName,
            DbaName = row.DbaName,
            RegistrationStatus = row.RegistrationStatus,
            RegistrationExpirationDate = row.RegistrationExpirationDate,
            PrimaryNaics = row.PrimaryNaics,
            EntityUrl = row.EntityUrl,
            RegisteredNaicsCodes = row.RegisteredNaicsCodes,
            SbaCertifications = row.SbaCertifications,
            BusinessTypeCodes = row.BusinessTypeCodes,
            FpdsContractCount = row.FpdsContractCount,
            FpdsTotalObligated = row.FpdsTotalObligated,
            FpdsObligated3yr = row.FpdsObligated3yr,
            FpdsObligated5yr = row.FpdsObligated5yr,
            FpdsCount3yr = row.FpdsCount3yr,
            FpdsCount5yr = row.FpdsCount5yr,
            FpdsAvgContractValue = row.FpdsAvgContractValue,
            FpdsMostRecentAward = row.FpdsMostRecentAward,
            FpdsTopNaics = row.FpdsTopNaics,
            FpdsTopAgencies = row.FpdsTopAgencies,
            UsaContractCount = row.UsaContractCount,
            UsaTotalObligated = row.UsaTotalObligated,
            UsaObligated3yr = row.UsaObligated3yr,
            UsaObligated5yr = row.UsaObligated5yr,
            UsaMostRecentAward = row.UsaMostRecentAward,
            UsaTopAgencies = row.UsaTopAgencies,
            SubContractCount = row.SubContractCount,
            SubTotalValue = row.SubTotalValue,
            SubAvgValue = row.SubAvgValue,
            PrimeSubAwardsCount = row.PrimeSubAwardsCount,
            PrimeSubTotalValue = row.PrimeSubTotalValue
        };
    }

    public async Task<List<AgencyBuyingPatternDto>> GetAgencyBuyingPatternsAsync(string agencyCode, int? year)
    {
        var query = _context.AgencyBuyingPatterns
            .AsNoTracking()
            .Where(p => p.AgencyId == agencyCode);

        if (year.HasValue)
            query = query.Where(p => p.AwardYear == year.Value);

        var rows = await query
            .OrderByDescending(p => p.AwardYear)
            .ThenBy(p => p.AwardQuarter)
            .ToListAsync();

        return rows.Select(p => new AgencyBuyingPatternDto
        {
            AgencyId = p.AgencyId,
            AgencyName = p.AgencyName,
            AwardYear = p.AwardYear,
            AwardQuarter = p.AwardQuarter,
            ContractCount = p.ContractCount,
            TotalObligated = p.TotalObligated,
            SmallBusinessPct = p.SmallBusinessPct,
            WosbPct = p.WosbPct,
            EightAPct = p.EightAPct,
            HubzonePct = p.HubzonePct,
            SdvosbPct = p.SdvosbPct,
            UnrestrictedPct = p.UnrestrictedPct,
            FullCompetitionPct = p.FullCompetitionPct,
            SoleSourcePct = p.SoleSourcePct,
            LimitedCompetitionPct = p.LimitedCompetitionPct,
            FfpPct = p.FfpPct,
            TmPct = p.TmPct,
            CostPlusPct = p.CostPlusPct,
            OtherTypePct = p.OtherTypePct
        }).ToList();
    }

    public async Task<ContractingOfficeProfileDto?> GetContractingOfficeProfileAsync(string officeCode)
    {
        var row = await _context.ContractingOfficeProfiles
            .AsNoTracking()
            .FirstOrDefaultAsync(o => o.ContractingOfficeId == officeCode);

        if (row == null)
            return null;

        return MapOfficeProfile(row);
    }

    public async Task<PagedResponse<ContractingOfficeProfileDto>> SearchContractingOfficesAsync(
        string? agencyCode, string? search, int page, int pageSize)
    {
        var query = _context.ContractingOfficeProfiles.AsNoTracking();

        if (!string.IsNullOrWhiteSpace(agencyCode))
            query = query.Where(o => o.ContractingOfficeId.StartsWith(agencyCode));

        if (!string.IsNullOrWhiteSpace(search))
            query = query.Where(o =>
                (o.ContractingOfficeName != null && o.ContractingOfficeName.Contains(search)) ||
                (o.AgencyName != null && o.AgencyName.Contains(search)));

        var totalCount = await query.CountAsync();

        var items = await query
            .OrderByDescending(o => o.TotalAwards)
            .Skip((page - 1) * pageSize)
            .Take(pageSize)
            .ToListAsync();

        return new PagedResponse<ContractingOfficeProfileDto>
        {
            Items = items.Select(MapOfficeProfile).ToList(),
            Page = page,
            PageSize = pageSize,
            TotalCount = totalCount
        };
    }

    private static ContractingOfficeProfileDto MapOfficeProfile(Core.Models.Views.ContractingOfficeProfileView row)
    {
        return new ContractingOfficeProfileDto
        {
            ContractingOfficeId = row.ContractingOfficeId,
            ContractingOfficeName = row.ContractingOfficeName,
            AgencyName = row.AgencyName,
            TotalAwards = row.TotalAwards,
            TotalObligated = row.TotalObligated,
            AvgAwardValue = row.AvgAwardValue,
            EarliestAward = row.EarliestAward,
            LatestAward = row.LatestAward,
            TopNaicsCodes = row.TopNaicsCodes,
            SmallBusinessPct = row.SmallBusinessPct,
            WosbPct = row.WosbPct,
            EightAPct = row.EightAPct,
            HubzonePct = row.HubzonePct,
            SdvosbPct = row.SdvosbPct,
            UnrestrictedPct = row.UnrestrictedPct,
            FfpPct = row.FfpPct,
            TmPct = row.TmPct,
            CostPlusPct = row.CostPlusPct,
            FullCompetitionPct = row.FullCompetitionPct,
            SoleSourcePct = row.SoleSourcePct,
            AvgProcurementDays = row.AvgProcurementDays
        };
    }
}
