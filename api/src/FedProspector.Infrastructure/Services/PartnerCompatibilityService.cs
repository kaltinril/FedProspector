using FedProspector.Core.DTOs.Intelligence;
using FedProspector.Core.Interfaces;
using FedProspector.Infrastructure.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;

namespace FedProspector.Infrastructure.Services;

public class PartnerCompatibilityService : IPartnerCompatibilityService
{
    private readonly FedProspectorDbContext _context;
    private readonly IOrganizationEntityService _orgEntityService;
    private readonly ILogger<PartnerCompatibilityService> _logger;

    public PartnerCompatibilityService(
        FedProspectorDbContext context,
        IOrganizationEntityService orgEntityService,
        ILogger<PartnerCompatibilityService> logger)
    {
        _context = context;
        _orgEntityService = orgEntityService;
        _logger = logger;
    }

    public async Task<PartnerScoreDto> ScorePartnerAsync(string partnerUei, string noticeId, int orgId)
    {
        var opp = await _context.Opportunities.AsNoTracking()
            .FirstOrDefaultAsync(o => o.NoticeId == noticeId)
            ?? throw new KeyNotFoundException($"Opportunity {noticeId} not found");

        var org = await _context.Organizations.AsNoTracking()
            .FirstOrDefaultAsync(o => o.OrganizationId == orgId)
            ?? throw new KeyNotFoundException($"Organization {orgId} not found");

        var linkedUeis = await _orgEntityService.GetLinkedUeisAsync(orgId);
        if (!string.IsNullOrEmpty(org.UeiSam) && !linkedUeis.Contains(org.UeiSam))
            linkedUeis.Add(org.UeiSam);

        var orgNaics = await _context.EntityNaicsCodes.AsNoTracking()
            .Where(n => linkedUeis.Contains(n.UeiSam))
            .Select(n => n.NaicsCode)
            .Distinct()
            .ToListAsync();

        var orgCerts = await _context.EntityBusinessTypes.AsNoTracking()
            .Where(b => linkedUeis.Contains(b.UeiSam))
            .Select(b => b.BusinessTypeCode)
            .Distinct()
            .ToListAsync();

        var agencyCode = ExtractAgencyCode(opp.FullParentPathCode);

        return await ScorePartnerInternalAsync(partnerUei, opp.NaicsCode, opp.SetAsideCode, agencyCode, linkedUeis, orgNaics, orgCerts);
    }

    public async Task<PartnerAnalysisDto> FindPartnersAsync(string noticeId, int orgId, int limit = 10)
    {
        var opp = await _context.Opportunities.AsNoTracking()
            .FirstOrDefaultAsync(o => o.NoticeId == noticeId)
            ?? throw new KeyNotFoundException($"Opportunity {noticeId} not found");

        var org = await _context.Organizations.AsNoTracking()
            .FirstOrDefaultAsync(o => o.OrganizationId == orgId)
            ?? throw new KeyNotFoundException($"Organization {orgId} not found");

        var linkedUeis = await _orgEntityService.GetLinkedUeisAsync(orgId);
        if (!string.IsNullOrEmpty(org.UeiSam) && !linkedUeis.Contains(org.UeiSam))
            linkedUeis.Add(org.UeiSam);

        var orgNaics = await _context.EntityNaicsCodes.AsNoTracking()
            .Where(n => linkedUeis.Contains(n.UeiSam))
            .Select(n => n.NaicsCode)
            .Distinct()
            .ToListAsync();

        var orgCerts = await _context.EntityBusinessTypes.AsNoTracking()
            .Where(b => linkedUeis.Contains(b.UeiSam))
            .Select(b => b.BusinessTypeCode)
            .Distinct()
            .ToListAsync();

        var agencyCode = ExtractAgencyCode(opp.FullParentPathCode);

        // Find candidate partners: entities that have been subs in relevant NAICS or agency
        var candidateUeis = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        // Past teaming partners (org was prime, they were sub or vice versa)
        if (linkedUeis.Count > 0)
        {
            var teamingPartners = await _context.SamSubawards.AsNoTracking()
                .Where(s => (s.PrimeUei != null && linkedUeis.Contains(s.PrimeUei) && s.SubUei != null)
                         || (s.SubUei != null && linkedUeis.Contains(s.SubUei) && s.PrimeUei != null))
                .Select(s => linkedUeis.Contains(s.PrimeUei!) ? s.SubUei! : s.PrimeUei!)
                .Distinct()
                .ToListAsync();

            foreach (var uei in teamingPartners)
                candidateUeis.Add(uei);
        }

        // Entities that have been subs in the same NAICS
        if (!string.IsNullOrEmpty(opp.NaicsCode))
        {
            var naicsSubs = await _context.SamSubawards.AsNoTracking()
                .Where(s => s.NaicsCode == opp.NaicsCode && s.SubUei != null)
                .Select(s => s.SubUei!)
                .Distinct()
                .Take(100)
                .ToListAsync();

            foreach (var uei in naicsSubs)
                candidateUeis.Add(uei);
        }

        // Entities that have been subs at the same agency
        if (!string.IsNullOrEmpty(agencyCode))
        {
            var agencySubs = await _context.SamSubawards.AsNoTracking()
                .Where(s => s.PrimeAgencyId == agencyCode && s.SubUei != null)
                .Select(s => s.SubUei!)
                .Distinct()
                .Take(100)
                .ToListAsync();

            foreach (var uei in agencySubs)
                candidateUeis.Add(uei);
        }

        // Remove own UEIs from candidates
        foreach (var uei in linkedUeis)
            candidateUeis.Remove(uei);

        _logger.LogInformation("Found {Count} candidate partners for opportunity {NoticeId}", candidateUeis.Count, noticeId);

        // Score each candidate
        var scored = new List<PartnerScoreDto>();
        foreach (var candidateUei in candidateUeis)
        {
            try
            {
                var score = await ScorePartnerInternalAsync(candidateUei, opp.NaicsCode, opp.SetAsideCode, agencyCode, linkedUeis, orgNaics, orgCerts);
                scored.Add(score);
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "Failed to score partner {Uei}", candidateUei);
            }
        }

        var topPartners = scored
            .OrderByDescending(p => p.PcsScore)
            .Take(limit)
            .ToList();

        return new PartnerAnalysisDto
        {
            NoticeId = noticeId,
            OrgId = orgId,
            TotalPartnersFound = candidateUeis.Count,
            Partners = topPartners
        };
    }

    private async Task<PartnerScoreDto> ScorePartnerInternalAsync(
        string partnerUei,
        string? oppNaicsCode,
        string? oppSetAsideCode,
        string? agencyCode,
        List<string> orgUeis,
        List<string> orgNaics,
        List<string> orgCerts)
    {
        // Get partner entity info
        var partnerEntity = await _context.Entities.AsNoTracking()
            .FirstOrDefaultAsync(e => e.UeiSam == partnerUei);

        var partnerName = partnerEntity?.LegalBusinessName ?? partnerUei;

        var factors = new List<PcsFactorDto>();

        // 1. Capability Complement (weight 0.25)
        var capFactor = await ScoreCapabilityComplementAsync(partnerUei, oppNaicsCode, orgNaics);
        factors.Add(capFactor);

        // 2. Agency Track Record (weight 0.25)
        var agencyFactor = await ScoreAgencyTrackRecordAsync(partnerUei, agencyCode);
        factors.Add(agencyFactor);

        // 3. Past Teaming History (weight 0.15)
        var teamingFactor = await ScorePastTeamingAsync(partnerUei, orgUeis);
        factors.Add(teamingFactor);

        // 4. Size Compatibility (weight 0.15)
        var sizeFactor = await ScoreSizeCompatibilityAsync(partnerUei, oppSetAsideCode);
        factors.Add(sizeFactor);

        // 5. Certification Complement (weight 0.10)
        var certFactor = await ScoreCertComplementAsync(partnerUei, oppSetAsideCode, orgCerts);
        factors.Add(certFactor);

        // 6. Clean Record (weight 0.10)
        var cleanFactor = await ScoreCleanRecordAsync(partnerUei, partnerEntity);
        factors.Add(cleanFactor);

        var totalScore = (int)Math.Round(factors.Sum(f => f.WeightedScore));
        totalScore = Math.Clamp(totalScore, 0, 100);

        var realDataCount = factors.Count(f => f.HadRealData);
        var confidence = realDataCount >= 5 ? "High" : realDataCount >= 3 ? "Medium" : "Low";
        var dataCompleteness = (int)Math.Round(realDataCount * 100.0 / factors.Count);

        var category = totalScore switch
        {
            >= 80 => "Ideal",
            >= 60 => "Strong",
            >= 40 => "Acceptable",
            _ => "Poor"
        };

        return new PartnerScoreDto
        {
            PartnerUei = partnerUei,
            PartnerName = partnerName,
            PcsScore = totalScore,
            Category = category,
            Confidence = confidence,
            DataCompletenessPercent = dataCompleteness,
            Factors = factors,
            PastTeamingCount = teamingFactor.Score switch
            {
                100 => 3,
                80 => 2,
                60 => 1,
                _ => 0
            },
            AgencyAwardCount = agencyFactor.Score switch
            {
                100 => 5,
                _ => (int)Math.Ceiling(agencyFactor.Score / 20.0)
            }
        };
    }

    private async Task<PcsFactorDto> ScoreCapabilityComplementAsync(string partnerUei, string? oppNaicsCode, List<string> orgNaics)
    {
        const decimal weight = 0.25m;

        var partnerNaics = await _context.EntityNaicsCodes.AsNoTracking()
            .Where(n => n.UeiSam == partnerUei)
            .Select(n => n.NaicsCode)
            .ToListAsync();

        if (partnerNaics.Count == 0)
        {
            return MakeFactor("Capability Complement", 40, weight, "No NAICS data available for partner", false);
        }

        if (!string.IsNullOrEmpty(oppNaicsCode) && partnerNaics.Contains(oppNaicsCode) && !orgNaics.Contains(oppNaicsCode))
        {
            return MakeFactor("Capability Complement", 100, weight,
                $"Partner has opportunity NAICS {oppNaicsCode} that org lacks — perfect complement");
        }

        // Check for related NAICS (same 2-digit prefix)
        var oppPrefix = oppNaicsCode?.Length >= 2 ? oppNaicsCode[..2] : null;
        if (oppPrefix != null && partnerNaics.Any(n => n.StartsWith(oppPrefix)) && !orgNaics.Any(n => n.StartsWith(oppPrefix)))
        {
            return MakeFactor("Capability Complement", 60, weight,
                $"Partner has related NAICS codes in sector {oppPrefix}");
        }

        // Partner has same NAICS as org (overlap, not complement)
        if (partnerNaics.Any(n => orgNaics.Contains(n)))
        {
            return MakeFactor("Capability Complement", 30, weight,
                "Partner NAICS overlaps with org — limited complementary value");
        }

        return MakeFactor("Capability Complement", 60, weight,
            "Partner has different NAICS codes that may complement org capabilities");
    }

    private async Task<PcsFactorDto> ScoreAgencyTrackRecordAsync(string partnerUei, string? agencyCode)
    {
        const decimal weight = 0.25m;

        if (string.IsNullOrEmpty(agencyCode))
        {
            return MakeFactor("Agency Track Record", 50, weight, "No agency code on opportunity", false);
        }

        var fiveYearsAgo = DateOnly.FromDateTime(DateTime.UtcNow.AddYears(-5));
        var count = await _context.FpdsContracts.AsNoTracking()
            .CountAsync(c => c.VendorUei == partnerUei
                          && c.AgencyId == agencyCode
                          && c.DateSigned != null
                          && c.DateSigned >= fiveYearsAgo);

        var score = count > 0
            ? Math.Clamp((int)(20 * count), 10, 100)
            : 10;

        var detail = count > 0
            ? $"Partner has {count} award(s) at this agency in last 5 years"
            : "No awards found at this agency in last 5 years";

        return MakeFactor("Agency Track Record", score, weight, detail, count > 0);
    }

    private async Task<PcsFactorDto> ScorePastTeamingAsync(string partnerUei, List<string> orgUeis)
    {
        const decimal weight = 0.15m;

        if (orgUeis.Count == 0)
        {
            return MakeFactor("Past Teaming History", 20, weight, "No org UEI — cannot check teaming history", false);
        }

        var teamingCount = await _context.SamSubawards.AsNoTracking()
            .CountAsync(s =>
                (s.PrimeUei != null && orgUeis.Contains(s.PrimeUei) && s.SubUei == partnerUei)
                || (s.SubUei != null && orgUeis.Contains(s.SubUei) && s.PrimeUei == partnerUei));

        int score;
        string detail;

        if (teamingCount >= 3)
        {
            score = 100;
            detail = $"Strong teaming history: {teamingCount} past subawards together";
        }
        else if (teamingCount == 2)
        {
            score = 80;
            detail = "Good teaming history: 2 past subawards together";
        }
        else if (teamingCount == 1)
        {
            score = 60;
            detail = "Some teaming history: 1 past subaward together";
        }
        else
        {
            score = 20;
            detail = "No prior teaming history found";
        }

        return MakeFactor("Past Teaming History", score, weight, detail, teamingCount > 0);
    }

    private async Task<PcsFactorDto> ScoreSizeCompatibilityAsync(string partnerUei, string? setAsideCode)
    {
        const decimal weight = 0.15m;

        // Full & open — size doesn't matter
        if (string.IsNullOrEmpty(setAsideCode))
        {
            return MakeFactor("Size Compatibility", 80, weight, "Full & open competition — size standard not a factor");
        }

        var partnerBusinessTypes = await _context.EntityBusinessTypes.AsNoTracking()
            .Where(b => b.UeiSam == partnerUei)
            .Select(b => b.BusinessTypeCode)
            .ToListAsync();

        if (partnerBusinessTypes.Count == 0)
        {
            return MakeFactor("Size Compatibility", 50, weight, "No business type data for partner", false);
        }

        var smallBizCodes = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
            { "2X", "8W", "A2", "23", "27", "A4", "QF", "A5", "XX" };

        var isSmall = partnerBusinessTypes.Any(b => smallBizCodes.Contains(b));

        if (isSmall)
        {
            return MakeFactor("Size Compatibility", 70, weight, "Partner is a small business — compatible for set-aside");
        }

        return MakeFactor("Size Compatibility", 40, weight, "Partner appears to be large business — may affect size standard eligibility");
    }

    private async Task<PcsFactorDto> ScoreCertComplementAsync(string partnerUei, string? setAsideCode, List<string> orgCerts)
    {
        const decimal weight = 0.10m;

        var partnerCerts = await _context.EntityBusinessTypes.AsNoTracking()
            .Where(b => b.UeiSam == partnerUei)
            .Select(b => b.BusinessTypeCode)
            .ToListAsync();

        if (partnerCerts.Count == 0)
        {
            return MakeFactor("Certification Complement", 20, weight, "No certification data for partner", false);
        }

        // Check if partner has certs the org doesn't
        var uniqueCerts = partnerCerts.Where(c => !orgCerts.Contains(c, StringComparer.OrdinalIgnoreCase)).ToList();

        if (uniqueCerts.Count > 0)
        {
            return MakeFactor("Certification Complement", 100, weight,
                $"Partner has {uniqueCerts.Count} certification(s) org lacks: {string.Join(", ", uniqueCerts.Take(5))}");
        }

        return MakeFactor("Certification Complement", 40, weight, "Partner certifications overlap with org — no added eligibility");
    }

    private async Task<PcsFactorDto> ScoreCleanRecordAsync(string partnerUei, Core.Models.Entity? partnerEntity)
    {
        const decimal weight = 0.10m;

        // Check exclusions
        var activeExclusion = await _context.SamExclusions.AsNoTracking()
            .AnyAsync(e => e.Uei == partnerUei
                        && (e.TerminationDate == null || e.TerminationDate >= DateOnly.FromDateTime(DateTime.UtcNow)));

        if (activeExclusion)
        {
            return MakeFactor("Clean Record", 0, weight, "Partner has an active exclusion — disqualifying");
        }

        var pastExclusion = await _context.SamExclusions.AsNoTracking()
            .AnyAsync(e => e.Uei == partnerUei
                        && e.TerminationDate != null
                        && e.TerminationDate < DateOnly.FromDateTime(DateTime.UtcNow));

        int score = 100;
        var details = new List<string>();

        if (pastExclusion)
        {
            score = 30;
            details.Add("Partner has a past exclusion (now terminated)");
        }

        // Check SAM registration status
        if (partnerEntity != null)
        {
            if (partnerEntity.RegistrationStatus == "A")
            {
                details.Add("Active SAM registration");
            }
            else
            {
                score = Math.Min(score, 20);
                details.Add("SAM registration is not active");
            }
        }
        else
        {
            details.Add("No entity record found in SAM");
        }

        var detail = details.Count > 0 ? string.Join("; ", details) : "No exclusion records; clean record";

        return MakeFactor("Clean Record", score, weight, detail);
    }

    private static PcsFactorDto MakeFactor(string name, int score, decimal weight, string detail, bool hadRealData = true)
    {
        return new PcsFactorDto
        {
            Name = name,
            Score = score,
            Weight = weight,
            WeightedScore = Math.Round(score * weight, 2),
            Detail = detail,
            HadRealData = hadRealData
        };
    }

    private static string? ExtractAgencyCode(string? fullParentPathCode)
    {
        if (string.IsNullOrWhiteSpace(fullParentPathCode))
            return null;

        var dotIndex = fullParentPathCode.IndexOf('.');
        return dotIndex > 0 ? fullParentPathCode[..dotIndex] : fullParentPathCode.Trim();
    }
}
