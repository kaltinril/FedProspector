using FedProspector.Core.DTOs;
using FedProspector.Core.DTOs.Intelligence;
using FedProspector.Core.Interfaces;
using FedProspector.Infrastructure.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;

namespace FedProspector.Infrastructure.Services;

public class TeamingService : ITeamingService
{
    private readonly FedProspectorDbContext _context;
    private readonly ILogger<TeamingService> _logger;

    public TeamingService(FedProspectorDbContext context, ILogger<TeamingService> logger)
    {
        _context = context;
        _logger = logger;
    }

    public async Task<PagedResponse<PartnerSearchResultDto>> SearchPartnersAsync(
        string? naicsCode, string? state, string? certification, string? agency, int page, int pageSize)
    {
        var query = _context.PartnerCapabilityMatches.AsNoTracking();

        if (!string.IsNullOrWhiteSpace(naicsCode))
            query = query.Where(p => p.NaicsCodes != null && p.NaicsCodes.Contains(naicsCode));

        if (!string.IsNullOrWhiteSpace(state))
            query = query.Where(p => p.State == state);

        if (!string.IsNullOrWhiteSpace(certification))
            query = query.Where(p => p.Certifications != null && p.Certifications.Contains(certification));

        if (!string.IsNullOrWhiteSpace(agency))
            query = query.Where(p => p.AgenciesWorkedWith != null && p.AgenciesWorkedWith.Contains(agency));

        var totalCount = await query.CountAsync();

        var items = await query
            .OrderByDescending(p => p.ContractCount)
            .ThenByDescending(p => p.TotalContractValue)
            .Skip((page - 1) * pageSize)
            .Take(pageSize)
            .ToListAsync();

        var dtos = items.Select(p => new PartnerSearchResultDto
        {
            UeiSam = p.UeiSam,
            LegalBusinessName = p.LegalBusinessName,
            State = p.State,
            NaicsCodes = p.NaicsCodes,
            PscCodes = p.PscCodes,
            Certifications = p.Certifications,
            AgenciesWorkedWith = p.AgenciesWorkedWith,
            PerformanceNaicsCodes = p.PerformanceNaicsCodes,
            ContractCount = p.ContractCount,
            TotalContractValue = p.TotalContractValue
        }).ToList();

        return new PagedResponse<PartnerSearchResultDto>
        {
            Items = dtos,
            Page = page,
            PageSize = pageSize,
            TotalCount = totalCount
        };
    }

    public async Task<PartnerRiskDto?> GetPartnerRiskAsync(string uei)
    {
        var row = await _context.PartnerRiskAssessments
            .AsNoTracking()
            .FirstOrDefaultAsync(r => r.UeiSam == uei);

        if (row == null)
            return null;

        var isCurrentExclusion = row.CurrentExclusionFlag != 0;
        var riskLevel = DetermineRiskLevel(isCurrentExclusion, row.TerminationForCauseCount,
            row.ExclusionCount, row.SpendingTrajectory, row.CustomerConcentrationPct);
        var riskSummary = BuildRiskSummary(isCurrentExclusion, row.TerminationForCauseCount,
            row.ExclusionCount, row.SpendingTrajectory, row.CustomerConcentrationPct);

        return new PartnerRiskDto
        {
            UeiSam = row.UeiSam,
            LegalBusinessName = row.LegalBusinessName,
            RiskLevel = riskLevel,
            RiskSummary = riskSummary,
            CurrentExclusionFlag = isCurrentExclusion,
            ExclusionCount = row.ExclusionCount,
            TerminationForCauseCount = row.TerminationForCauseCount,
            SpendingTrajectory = row.SpendingTrajectory,
            Recent2yrValue = row.Recent2yrValue,
            Prior2yrValue = row.Prior2yrValue,
            TopAgencyName = row.TopAgencyName,
            CustomerConcentrationPct = row.CustomerConcentrationPct,
            CertificationCount = row.CertificationCount,
            TotalContractValue = row.TotalContractValue,
            YearsInBusiness = row.YearsInBusiness
        };
    }

    public async Task<PagedResponse<MentorProtegePairDto>> GetMentorProtegeCandidatesAsync(
        string? protegeUei, string? naicsCode, int page, int pageSize)
    {
        var query = _context.MentorProtegeCandidates.AsNoTracking();

        if (!string.IsNullOrWhiteSpace(protegeUei))
            query = query.Where(m => m.ProtegeUei == protegeUei);

        if (!string.IsNullOrWhiteSpace(naicsCode))
            query = query.Where(m => m.SharedNaics == naicsCode);

        var totalCount = await query.CountAsync();

        var items = await query
            .OrderByDescending(m => m.MentorTotalValue)
            .Skip((page - 1) * pageSize)
            .Take(pageSize)
            .ToListAsync();

        var dtos = items.Select(m => new MentorProtegePairDto
        {
            ProtegeUei = m.ProtegeUei,
            ProtegeName = m.ProtegeName,
            ProtegeCertifications = m.ProtegeCertifications,
            ProtegeNaics = m.ProtegeNaics,
            ProtegeContractCount = m.ProtegeContractCount,
            ProtegeTotalValue = m.ProtegeTotalValue,
            MentorUei = m.MentorUei,
            MentorName = m.MentorName,
            SharedNaics = m.SharedNaics,
            MentorContractCount = m.MentorContractCount,
            MentorTotalValue = m.MentorTotalValue,
            MentorAgencies = m.MentorAgencies
        }).ToList();

        return new PagedResponse<MentorProtegePairDto>
        {
            Items = dtos,
            Page = page,
            PageSize = pageSize,
            TotalCount = totalCount
        };
    }

    public async Task<PagedResponse<PrimeSubRelationshipDto>> GetPrimeSubRelationshipsAsync(
        string uei, int page, int pageSize)
    {
        var query = _context.PrimeSubRelationships
            .AsNoTracking()
            .Where(r => r.PrimeUei == uei || r.SubUei == uei);

        var totalCount = await query.CountAsync();

        var items = await query
            .OrderByDescending(r => r.SubawardCount)
            .ThenByDescending(r => r.TotalSubawardValue)
            .Skip((page - 1) * pageSize)
            .Take(pageSize)
            .ToListAsync();

        var dtos = items.Select(r => new PrimeSubRelationshipDto
        {
            PrimeUei = r.PrimeUei,
            PrimeName = r.PrimeName,
            SubUei = r.SubUei,
            SubName = r.SubName,
            SubawardCount = r.SubawardCount,
            TotalSubawardValue = r.TotalSubawardValue,
            AvgSubawardValue = r.AvgSubawardValue,
            FirstSubawardDate = r.FirstSubawardDate,
            LastSubawardDate = r.LastSubawardDate,
            NaicsCodesTogether = r.NaicsCodesTogether,
            AgenciesTogether = r.AgenciesTogether
        }).ToList();

        return new PagedResponse<PrimeSubRelationshipDto>
        {
            Items = dtos,
            Page = page,
            PageSize = pageSize,
            TotalCount = totalCount
        };
    }

    public async Task<List<TeamingNetworkNodeDto>> GetTeamingNetworkAsync(string uei, int depth)
    {
        // Clamp depth to 1 or 2
        depth = Math.Clamp(depth, 1, 2);

        // First hop: direct relationships
        var hop1 = await _context.TeamingNetwork
            .AsNoTracking()
            .Where(n => n.VendorUei == uei)
            .Take(200)
            .ToListAsync();

        var results = hop1.Select(n => new TeamingNetworkNodeDto
        {
            VendorUei = n.VendorUei,
            VendorName = n.VendorName,
            RelationshipDirection = n.RelationshipDirection,
            PartnerUei = n.PartnerUei,
            PartnerName = n.PartnerName,
            AwardCount = n.AwardCount,
            TotalValue = n.TotalValue
        }).ToList();

        if (depth >= 2 && hop1.Count > 0)
        {
            var hop1PartnerUeis = hop1.Select(n => n.PartnerUei).Distinct().ToList();

            var hop2 = await _context.TeamingNetwork
                .AsNoTracking()
                .Where(n => hop1PartnerUeis.Contains(n.VendorUei) && n.PartnerUei != uei)
                .Take(500)
                .ToListAsync();

            results.AddRange(hop2.Select(n => new TeamingNetworkNodeDto
            {
                VendorUei = n.VendorUei,
                VendorName = n.VendorName,
                RelationshipDirection = n.RelationshipDirection,
                PartnerUei = n.PartnerUei,
                PartnerName = n.PartnerName,
                AwardCount = n.AwardCount,
                TotalValue = n.TotalValue
            }));
        }

        return results;
    }

    public async Task<PartnerGapAnalysisDto> GetPartnerGapAnalysisAsync(int organizationId, string? naicsCode)
    {
        // Get the org's NAICS codes
        var orgNaics = await _context.OrganizationNaics
            .AsNoTracking()
            .Where(n => n.OrganizationId == organizationId)
            .Select(n => n.NaicsCode)
            .ToListAsync();

        if (orgNaics.Count == 0)
        {
            return new PartnerGapAnalysisDto
            {
                OrganizationId = organizationId,
                OrgNaicsCodes = [],
                GapFillingPartners = []
            };
        }

        // Find partners that have capabilities the org lacks
        var query = _context.PartnerCapabilityMatches.AsNoTracking();

        if (!string.IsNullOrWhiteSpace(naicsCode))
        {
            // Find partners who have this specific NAICS that the org may not
            query = query.Where(p => p.NaicsCodes != null && p.NaicsCodes.Contains(naicsCode));
        }

        // Exclude the org's own entities
        var orgUeis = await _context.OrganizationEntities
            .AsNoTracking()
            .Where(oe => oe.OrganizationId == organizationId)
            .Select(oe => oe.UeiSam)
            .ToListAsync();

        if (orgUeis.Count > 0)
            query = query.Where(p => !orgUeis.Contains(p.UeiSam));

        // Only include partners with contract history
        query = query.Where(p => p.ContractCount > 0);

        var partners = await query
            .OrderByDescending(p => p.ContractCount)
            .Take(50)
            .ToListAsync();

        // Filter to partners whose NAICS codes do not fully overlap with the org's
        var gapPartners = partners
            .Where(p =>
            {
                if (string.IsNullOrEmpty(p.NaicsCodes)) return false;
                var partnerNaicsList = p.NaicsCodes.Split(',', StringSplitOptions.TrimEntries | StringSplitOptions.RemoveEmptyEntries);
                return partnerNaicsList.Any(n => !orgNaics.Contains(n));
            })
            .Select(p => new PartnerSearchResultDto
            {
                UeiSam = p.UeiSam,
                LegalBusinessName = p.LegalBusinessName,
                State = p.State,
                NaicsCodes = p.NaicsCodes,
                PscCodes = p.PscCodes,
                Certifications = p.Certifications,
                AgenciesWorkedWith = p.AgenciesWorkedWith,
                PerformanceNaicsCodes = p.PerformanceNaicsCodes,
                ContractCount = p.ContractCount,
                TotalContractValue = p.TotalContractValue
            })
            .Take(25)
            .ToList();

        return new PartnerGapAnalysisDto
        {
            OrganizationId = organizationId,
            OrgNaicsCodes = orgNaics,
            GapFillingPartners = gapPartners
        };
    }

    private static string DetermineRiskLevel(bool currentExclusion, int terminationForCauseCount,
        int exclusionCount, string? spendingTrajectory, decimal customerConcentrationPct)
    {
        // RED
        if (currentExclusion || terminationForCauseCount > 0 || customerConcentrationPct > 80)
            return "RED";

        // YELLOW
        if (exclusionCount > 0 || spendingTrajectory == "DECLINING" || customerConcentrationPct > 50)
            return "YELLOW";

        return "GREEN";
    }

    private static string BuildRiskSummary(bool currentExclusion, int terminationForCauseCount,
        int exclusionCount, string? spendingTrajectory, decimal customerConcentrationPct)
    {
        var issues = new List<string>();

        if (currentExclusion)
            issues.Add("Currently excluded from federal contracting");
        if (terminationForCauseCount > 0)
            issues.Add($"{terminationForCauseCount} termination(s) for cause");
        if (customerConcentrationPct > 80)
            issues.Add($"Extreme customer concentration ({customerConcentrationPct:F1}%)");
        else if (customerConcentrationPct > 50)
            issues.Add($"High customer concentration ({customerConcentrationPct:F1}%)");
        if (exclusionCount > 0 && !currentExclusion)
            issues.Add($"{exclusionCount} past exclusion(s)");
        if (spendingTrajectory == "DECLINING")
            issues.Add("Declining spending trajectory");

        return issues.Count > 0
            ? string.Join("; ", issues)
            : "No significant risk factors identified";
    }
}
