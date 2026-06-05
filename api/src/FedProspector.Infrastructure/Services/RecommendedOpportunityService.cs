using FedProspector.Core.Constants;
using FedProspector.Core.DTOs.Intelligence;
using FedProspector.Core.Interfaces;
using FedProspector.Infrastructure.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;

namespace FedProspector.Infrastructure.Services;

public class RecommendedOpportunityService : IRecommendedOpportunityService
{
    private readonly FedProspectorDbContext _context;
    private readonly ILogger<RecommendedOpportunityService> _logger;

    /// <summary>
    /// Maps set-aside codes to the certification types they require.
    /// </summary>
    private static readonly Dictionary<string, string> SetAsideToCertType = new(StringComparer.OrdinalIgnoreCase)
    {
        ["WOSB"] = "WOSB",
        ["WOSBSS"] = "WOSB",
        ["EDWOSB"] = "EDWOSB",
        ["EDWOSBSS"] = "EDWOSB",
        ["8A"] = "8(a)",
        ["8AN"] = "8(a)",
        ["SBA"] = "SDB",
        ["SBP"] = "SDB",
        ["HZC"] = "HUBZone",
        ["HZS"] = "HUBZone",
        ["SDVOSBC"] = "SDVOSB",
        ["SDVOSBS"] = "SDVOSB",
    };

    /// <summary>
    /// Phase 136 Unit C — notice types treated as ungated "market research" (pre-RFP
    /// signals where no bid is yet possible, so win-probability is irrelevant).
    /// </summary>
    private static readonly HashSet<string> MarketResearchTypes = new(StringComparer.OrdinalIgnoreCase)
    {
        "Sources Sought",
        "Special Notice",
    };

    /// <summary>OQS factor weights (must sum to 1.0).</summary>
    private const decimal WeightProfileMatch = 0.20m;
    private const decimal WeightValueAlignment = 0.15m;
    private const decimal WeightCompetition = 0.10m;
    private const decimal WeightTimeline = 0.15m;
    private const decimal WeightReuse = 0.10m;
    private const decimal WeightGrowth = 0.15m;
    private const decimal WeightRecompete = 0.15m;

    public RecommendedOpportunityService(
        FedProspectorDbContext context,
        ILogger<RecommendedOpportunityService> logger)
    {
        _context = context;
        _logger = logger;
    }

    public async Task<List<RecommendedOpportunityDto>> GetRecommendedAsync(
        int orgId, int limit = 10, int? userId = null, bool includeClearanceRequired = false)
    {
        if (limit < 1) limit = 1;
        if (limit > 100) limit = 100;

        // 1. Load org NAICS codes and certifications
        var orgNaicsList = await _context.OrganizationNaics.AsNoTracking()
            .Where(n => n.OrganizationId == orgId)
            .Select(n => new { n.NaicsCode, n.IsPrimary })
            .ToListAsync();

        if (orgNaicsList.Count == 0)
        {
            _logger.LogInformation("Org {OrgId} has no NAICS codes — no recommendations", orgId);
            return [];
        }

        var naicsCodes = orgNaicsList.Select(n => n.NaicsCode).ToList();
        var primaryNaics = orgNaicsList
            .Where(n => n.IsPrimary == "Y")
            .Select(n => n.NaicsCode)
            .ToHashSet(StringComparer.OrdinalIgnoreCase);

        var orgCerts = await _context.OrganizationCertifications.AsNoTracking()
            .Where(c => c.OrganizationId == orgId && c.IsActive == "Y")
            .Select(c => c.CertificationType)
            .ToListAsync();

        var orgCertSet = orgCerts.ToHashSet(StringComparer.OrdinalIgnoreCase);

        // Phase 136 Unit G: associated NAICS expand which opportunities surface
        // (candidate selection) but are scored as a distinct, lower tier (see ScoreProfileMatch).
        var associatedNaics = (await _context.OrganizationAssociatedNaics.AsNoTracking()
            .Where(n => n.OrganizationId == orgId)
            .Select(n => n.NaicsCode)
            .ToListAsync())
            .ToHashSet(StringComparer.OrdinalIgnoreCase);
        var candidateNaics = naicsCodes.Concat(associatedNaics).Distinct().ToList();

        // 2. Pre-load org context data for OQS factors
        var orgContext = await LoadOrgContextAsync(orgId, naicsCodes);

        // 3. Query active opportunities matching org NAICS codes (registered + associated)
        var now = DateTime.UtcNow;
        var candidates = await _context.Opportunities.AsNoTracking()
            .Where(o => candidateNaics.Contains(o.NaicsCode!)
                        && o.Active != "N"
                        && !OpportunityFilters.NonBiddableTypes.Contains(o.Type!)
                        && (o.ResponseDeadline == null || o.ResponseDeadline > now))
            .Select(o => new
            {
                o.NoticeId,
                o.Title,
                o.SolicitationNumber,
                o.DepartmentName,
                o.DepartmentCgac,
                o.SubTier,
                o.ContractingOfficeId,
                o.SetAsideCode,
                o.SetAsideDescription,
                o.NaicsCode,
                o.ClassificationCode,
                o.Type,
                o.EstimatedContractValue,
                o.AwardAmount,
                PostedDate = o.PostedDate,
                o.ResponseDeadline,
                o.PopState,
                o.PopCity,
                o.PopCountry,
                o.FhOrgId
            })
            .ToListAsync();

        // 3b. Exclude ignored opportunities
        if (userId.HasValue)
        {
            var ignoredIds = await _context.OpportunityIgnores
                .Where(i => i.UserId == userId.Value)
                .Select(i => i.NoticeId)
                .ToListAsync();

            if (ignoredIds.Count > 0)
            {
                var ignoredSet = ignoredIds.ToHashSet();
                candidates = candidates.Where(c => !ignoredSet.Contains(c.NoticeId)).ToList();
            }
        }

        // 4. Dedup: keep latest notice per solicitation
        var deduped = candidates
            .GroupBy(c => string.IsNullOrEmpty(c.SolicitationNumber) ? c.NoticeId : c.SolicitationNumber)
            .Select(g => g.OrderByDescending(c => c.PostedDate).ThenByDescending(c => c.NoticeId).First())
            .ToList();

        // 5. Batch-load intel summaries for re-compete data AND the Phase 136 Unit B
        // clearance signal. A notice is "high-confidence clearance required" if ANY of
        // its opportunity_attachment_summary rows has clearance_required='Y' AND
        // overall_confidence='high'. CAVEAT: only document-analyzed opps carry this
        // signal at all — absence means "no high-confidence signal", not "no clearance".
        var noticeIds = deduped.Select(d => d.NoticeId).ToList();
        var intelByNotice = await _context.OpportunityAttachmentSummaries.AsNoTracking()
            .Where(s => noticeIds.Contains(s.NoticeId))
            .GroupBy(s => s.NoticeId)
            .Select(g => new
            {
                NoticeId = g.Key,
                IsRecompete = g.Max(s => s.IsRecompete),
                IncumbentName = g.Where(s => s.IncumbentName != null)
                    .OrderByDescending(s => s.ExtractedAt)
                    .Select(s => s.IncumbentName)
                    .FirstOrDefault(),
                ClearanceRequiredHighConf = g.Any(s =>
                    s.ClearanceRequired != null && s.ClearanceRequired.ToUpper() == "Y"
                    && s.OverallConfidence != null && s.OverallConfidence.ToLower() == "high")
            })
            .ToDictionaryAsync(x => x.NoticeId);

        // 6. Load competition data from pre-computed summary table (sub-millisecond)
        var distinctNaicsInCandidates = deduped
            .Where(c => c.NaicsCode != null)
            .Select(c => c.NaicsCode!)
            .Distinct()
            .ToList();

        var competitionData = await _context.UsaspendingAwardSummaries.AsNoTracking()
            .Where(s => distinctNaicsInCandidates.Contains(s.NaicsCode))
            .Select(s => new { s.NaicsCode, s.AgencyCgac, s.VendorCount })
            .ToListAsync();

        var competitionLookup = competitionData.ToDictionary(
            c => (c.NaicsCode, c.AgencyCgac),
            c => c.VendorCount);

        // 7. Score each candidate using the 7-factor OQS model
        var scored = new List<(RecommendedOpportunityDto Dto, decimal? Score, bool ClearanceRequired)>();

        foreach (var c in deduped)
        {
            var setAsideCode = (c.SetAsideCode ?? "").Trim();

            // Set-aside filtering: skip if requires a cert we don't have
            if (!string.IsNullOrEmpty(setAsideCode)
                && SetAsideToCertType.TryGetValue(setAsideCode, out var requiredCert)
                && !orgCertSet.Contains(requiredCert))
            {
                continue;
            }

            var value = c.EstimatedContractValue ?? c.AwardAmount;
            int? daysRemaining = c.ResponseDeadline.HasValue
                ? Math.Max(0, (int)(c.ResponseDeadline.Value - now).TotalDays)
                : null;

            // Determine re-compete status and clearance signal from intel
            var isRecompete = false;
            string? incumbentName = null;
            var clearanceRequired = false;
            if (intelByNotice.TryGetValue(c.NoticeId, out var intel))
            {
                isRecompete = string.Equals(intel.IsRecompete, "Y", StringComparison.OrdinalIgnoreCase);
                incumbentName = intel.IncumbentName;
                clearanceRequired = intel.ClearanceRequiredHighConf;
            }

            // Factor 1: Profile Match Strength
            var profileFactor = ScoreProfileMatch(c.NaicsCode, setAsideCode, primaryNaics, orgCertSet, associatedNaics);

            // Factor 2: Estimated Value Alignment
            var valueFactor = ScoreValueAlignment(value, orgContext.AvgAwardValue, orgContext.HasAwardData);

            // Factor 3: Competition Level
            var competitionKey = (c.NaicsCode ?? "", c.DepartmentCgac ?? "");
            competitionLookup.TryGetValue(competitionKey, out var vendorCount);
            var competitionFactor = ScoreCompetition(vendorCount);

            // Factor 4: Timeline Feasibility
            var timelineFactor = ScoreTimeline(daysRemaining);

            // Factor 5: Reuse Potential
            var reuseFactor = ScoreReusePotential(c.NaicsCode, c.DepartmentName, orgContext);

            // Factor 6: Growth Potential
            var growthFactor = ScoreGrowthPotential(c.NaicsCode, c.DepartmentName, orgContext);

            // Factor 7: Re-compete Advantage
            var recompeteFactor = ScoreRecompeteAdvantage(isRecompete, incumbentName, orgContext);

            // Calculate weighted OQS
            var factors = new List<OqScoreFactorDto>
            {
                BuildFactor("Profile Match", profileFactor.Score, WeightProfileMatch, profileFactor.Detail, profileFactor.HadRealData),
                BuildFactor("Value Alignment", valueFactor.Score, WeightValueAlignment, valueFactor.Detail, valueFactor.HadRealData),
                BuildFactor("Competition Level", competitionFactor.Score, WeightCompetition, competitionFactor.Detail, competitionFactor.HadRealData),
                BuildFactor("Timeline Feasibility", timelineFactor.Score, WeightTimeline, timelineFactor.Detail, timelineFactor.HadRealData),
                BuildFactor("Reuse Potential", reuseFactor.Score, WeightReuse, reuseFactor.Detail, reuseFactor.HadRealData),
                BuildFactor("Growth Potential", growthFactor.Score, WeightGrowth, growthFactor.Detail, growthFactor.HadRealData),
                BuildFactor("Re-compete Advantage", recompeteFactor.Score, WeightRecompete, recompeteFactor.Detail, recompeteFactor.HadRealData),
            };

            // Phase 136 Unit D: renormalize over real-data factors only; null => insufficient data.
            var oqScore = ComputeRenormalizedScore(factors);
            var realDataCount = factors.Count(f => f.HadRealData);
            var confidence = realDataCount >= 6 ? "High" : realDataCount >= 4 ? "Medium" : "Low";

            var category = CategoryFor(oqScore);

            var dto = new RecommendedOpportunityDto
            {
                NoticeId = c.NoticeId,
                Title = c.Title,
                SolicitationNumber = c.SolicitationNumber,
                DepartmentName = c.DepartmentName,
                SubTier = c.SubTier,
                ContractingOfficeId = c.ContractingOfficeId,
                SetAsideCode = c.SetAsideCode,
                SetAsideDescription = c.SetAsideDescription,
                NaicsCode = c.NaicsCode,
                ClassificationCode = c.ClassificationCode,
                NoticeType = c.Type,
                AwardAmount = c.AwardAmount,
                PostedDate = c.PostedDate.HasValue
                    ? c.PostedDate.Value.ToDateTime(TimeOnly.MinValue)
                    : null,
                ResponseDeadline = c.ResponseDeadline,
                DaysRemaining = daysRemaining,
                PopState = c.PopState,
                PopCity = c.PopCity,
                PopCountry = c.PopCountry,
                FhOrgId = c.FhOrgId,
                OqScore = oqScore,
                OqScoreCategory = category,
                OqScoreFactors = factors,
                Confidence = confidence,
                IsRecompete = isRecompete,
                IncumbentName = incumbentName,
                ClearanceRequired = clearanceRequired,
            };

            scored.Add((dto, oqScore, clearanceRequired));
        }

        // 8. Phase 136 Unit B: ALWAYS compute the ranked top-N over the
        // clearance-EXCLUDED set so high-confidence clearance-required notices never
        // consume top-N slots. A null OQS (insufficient data) sorts last.
        var ranked = scored
            .Where(s => !s.ClearanceRequired)
            .OrderByDescending(s => s.Score ?? decimal.MinValue)
            .Take(limit)
            .Select(s => s.Dto)
            .ToList();

        // When requested, append the clearance-required matches as a separate additive
        // group AFTER the ranked top-N (flagged via ClearanceRequired). They do not
        // displace or count toward the top-N. When not requested, they are hidden.
        var topN = ranked;
        if (includeClearanceRequired)
        {
            var clearanceGroup = scored
                .Where(s => s.ClearanceRequired)
                .OrderByDescending(s => s.Score ?? decimal.MinValue)
                .Select(s => s.Dto)
                .ToList();
            topN = ranked.Concat(clearanceGroup).ToList();
        }

        // 9. Enrich with NAICS descriptions (batch lookup)
        var distinctNaics = topN
            .Where(d => d.NaicsCode != null)
            .Select(d => d.NaicsCode!)
            .Distinct()
            .ToList();

        var naicsDescriptions = await _context.RefNaicsCodes.AsNoTracking()
            .Where(n => distinctNaics.Contains(n.NaicsCode))
            .ToDictionaryAsync(n => n.NaicsCode, n => n.Description);

        // 10. Enrich: check re-compete from FPDS for any that didn't get intel-based re-compete
        var solNums = topN
            .Where(d => !d.IsRecompete && !string.IsNullOrEmpty(d.SolicitationNumber))
            .Select(d => d.SolicitationNumber!)
            .Distinct()
            .ToList();

        var incumbents = solNums.Count > 0
            ? await _context.FpdsContracts.AsNoTracking()
                .Where(c => solNums.Contains(c.SolicitationNumber!))
                .GroupBy(c => c.SolicitationNumber)
                .Select(g => new
                {
                    SolicitationNumber = g.Key,
                    VendorName = g.OrderByDescending(c => c.DateSigned).First().VendorName
                })
                .ToDictionaryAsync(x => x.SolicitationNumber!, x => x.VendorName)
            : new Dictionary<string, string?>();

        // 11. Apply enrichments
        foreach (var dto in topN)
        {
            if (dto.NaicsCode != null && naicsDescriptions.TryGetValue(dto.NaicsCode, out var desc))
                dto.NaicsDescription = desc;

            if (!dto.IsRecompete
                && !string.IsNullOrEmpty(dto.SolicitationNumber)
                && incumbents.TryGetValue(dto.SolicitationNumber, out var vendorName))
            {
                dto.IsRecompete = true;
                dto.IncumbentName = vendorName;
            }
        }

        _logger.LogInformation(
            "Recommended {Count} opportunities for org {OrgId} (from {Total} candidates, {Deduped} after dedup)",
            topN.Count, orgId, candidates.Count, deduped.Count);

        return topN;
    }

    public async Task<RecommendedOpportunityDto?> CalculateOqScoreAsync(string noticeId, int orgId)
    {
        // 1. Load org NAICS codes and certifications
        var orgNaicsList = await _context.OrganizationNaics.AsNoTracking()
            .Where(n => n.OrganizationId == orgId)
            .Select(n => new { n.NaicsCode, n.IsPrimary })
            .ToListAsync();

        if (orgNaicsList.Count == 0)
            return null;

        var naicsCodes = orgNaicsList.Select(n => n.NaicsCode).ToList();
        var primaryNaics = orgNaicsList
            .Where(n => n.IsPrimary == "Y")
            .Select(n => n.NaicsCode)
            .ToHashSet(StringComparer.OrdinalIgnoreCase);

        var orgCerts = await _context.OrganizationCertifications.AsNoTracking()
            .Where(c => c.OrganizationId == orgId && c.IsActive == "Y")
            .Select(c => c.CertificationType)
            .ToListAsync();
        var orgCertSet = orgCerts.ToHashSet(StringComparer.OrdinalIgnoreCase);

        // Phase 136 Unit G: associated NAICS scored as a distinct, lower tier (see ScoreProfileMatch).
        var associatedNaics = (await _context.OrganizationAssociatedNaics.AsNoTracking()
            .Where(n => n.OrganizationId == orgId)
            .Select(n => n.NaicsCode)
            .ToListAsync())
            .ToHashSet(StringComparer.OrdinalIgnoreCase);

        // 2. Load the opportunity
        var now = DateTime.UtcNow;
        var opp = await _context.Opportunities.AsNoTracking()
            .Where(o => o.NoticeId == noticeId)
            .Select(o => new
            {
                o.NoticeId,
                o.Title,
                o.SolicitationNumber,
                o.DepartmentName,
                o.DepartmentCgac,
                o.SubTier,
                o.ContractingOfficeId,
                o.SetAsideCode,
                o.SetAsideDescription,
                o.NaicsCode,
                o.ClassificationCode,
                o.Type,
                o.EstimatedContractValue,
                o.AwardAmount,
                PostedDate = o.PostedDate,
                o.ResponseDeadline,
                o.PopState,
                o.PopCity,
                o.PopCountry,
                o.FhOrgId
            })
            .FirstOrDefaultAsync();

        if (opp == null) return null;

        // 3. Load org context
        var orgContext = await LoadOrgContextAsync(orgId, naicsCodes);

        // 4. Load intel for re-compete
        var intel = await _context.OpportunityAttachmentSummaries.AsNoTracking()
            .Where(s => s.NoticeId == noticeId)
            .OrderByDescending(s => s.ExtractedAt)
            .Select(s => new { s.IsRecompete, s.IncumbentName })
            .FirstOrDefaultAsync();

        var isRecompete = string.Equals(intel?.IsRecompete, "Y", StringComparison.OrdinalIgnoreCase);
        var incumbentName = intel?.IncumbentName;

        // Phase 136 Unit B clearance signal: high-confidence clearance-required if ANY
        // analyzed attachment row says so. CAVEAT: only document-analyzed opps carry this.
        var clearanceRequired = await _context.OpportunityAttachmentSummaries.AsNoTracking()
            .AnyAsync(s => s.NoticeId == noticeId
                && s.ClearanceRequired != null && s.ClearanceRequired.ToUpper() == "Y"
                && s.OverallConfidence != null && s.OverallConfidence.ToLower() == "high");

        // 5. Load competition data from pre-computed summary table
        var vendorCount = 0;
        if (!string.IsNullOrEmpty(opp.NaicsCode) && !string.IsNullOrEmpty(opp.DepartmentCgac))
        {
            vendorCount = await _context.UsaspendingAwardSummaries.AsNoTracking()
                .Where(s => s.NaicsCode == opp.NaicsCode && s.AgencyCgac == opp.DepartmentCgac)
                .Select(s => s.VendorCount)
                .FirstOrDefaultAsync();
        }

        // 6. Score using 7-factor model
        var setAsideCode = (opp.SetAsideCode ?? "").Trim();
        var value = opp.EstimatedContractValue ?? opp.AwardAmount;
        int? daysRemaining = opp.ResponseDeadline.HasValue
            ? Math.Max(0, (int)(opp.ResponseDeadline.Value - now).TotalDays)
            : null;

        var profileFactor = ScoreProfileMatch(opp.NaicsCode, setAsideCode, primaryNaics, orgCertSet, associatedNaics);
        var valueFactor = ScoreValueAlignment(value, orgContext.AvgAwardValue, orgContext.HasAwardData);
        var competitionFactor = ScoreCompetition(vendorCount);
        var timelineFactor = ScoreTimeline(daysRemaining);
        var reuseFactor = ScoreReusePotential(opp.NaicsCode, opp.DepartmentName, orgContext);
        var growthFactor = ScoreGrowthPotential(opp.NaicsCode, opp.DepartmentName, orgContext);
        var recompeteFactor = ScoreRecompeteAdvantage(isRecompete, incumbentName, orgContext);

        var factors = new List<OqScoreFactorDto>
        {
            BuildFactor("Profile Match", profileFactor.Score, WeightProfileMatch, profileFactor.Detail, profileFactor.HadRealData),
            BuildFactor("Value Alignment", valueFactor.Score, WeightValueAlignment, valueFactor.Detail, valueFactor.HadRealData),
            BuildFactor("Competition Level", competitionFactor.Score, WeightCompetition, competitionFactor.Detail, competitionFactor.HadRealData),
            BuildFactor("Timeline Feasibility", timelineFactor.Score, WeightTimeline, timelineFactor.Detail, timelineFactor.HadRealData),
            BuildFactor("Reuse Potential", reuseFactor.Score, WeightReuse, reuseFactor.Detail, reuseFactor.HadRealData),
            BuildFactor("Growth Potential", growthFactor.Score, WeightGrowth, growthFactor.Detail, growthFactor.HadRealData),
            BuildFactor("Re-compete Advantage", recompeteFactor.Score, WeightRecompete, recompeteFactor.Detail, recompeteFactor.HadRealData),
        };

        // Phase 136 Unit D: renormalize over real-data factors only; null => insufficient data.
        var oqScore = ComputeRenormalizedScore(factors);
        var realDataCount = factors.Count(f => f.HadRealData);
        var confidence = realDataCount >= 6 ? "High" : realDataCount >= 4 ? "Medium" : "Low";
        var category = CategoryFor(oqScore);

        // 7. NAICS description
        string? naicsDescription = null;
        if (!string.IsNullOrEmpty(opp.NaicsCode))
        {
            naicsDescription = await _context.RefNaicsCodes.AsNoTracking()
                .Where(n => n.NaicsCode == opp.NaicsCode)
                .Select(n => n.Description)
                .FirstOrDefaultAsync();
        }

        return new RecommendedOpportunityDto
        {
            NoticeId = opp.NoticeId,
            Title = opp.Title,
            SolicitationNumber = opp.SolicitationNumber,
            DepartmentName = opp.DepartmentName,
            SubTier = opp.SubTier,
            ContractingOfficeId = opp.ContractingOfficeId,
            SetAsideCode = opp.SetAsideCode,
            SetAsideDescription = opp.SetAsideDescription,
            NaicsCode = opp.NaicsCode,
            NaicsDescription = naicsDescription,
            ClassificationCode = opp.ClassificationCode,
            NoticeType = opp.Type,
            AwardAmount = opp.AwardAmount,
            PostedDate = opp.PostedDate.HasValue
                ? opp.PostedDate.Value.ToDateTime(TimeOnly.MinValue)
                : null,
            ResponseDeadline = opp.ResponseDeadline,
            DaysRemaining = daysRemaining,
            PopState = opp.PopState,
            PopCity = opp.PopCity,
            PopCountry = opp.PopCountry,
            FhOrgId = opp.FhOrgId,
            OqScore = oqScore,
            OqScoreCategory = category,
            OqScoreFactors = factors,
            Confidence = confidence,
            IsRecompete = isRecompete,
            IncumbentName = incumbentName,
            ClearanceRequired = clearanceRequired,
        };
    }

    // ────────────────────────────────────────────────────────────────────
    // Phase 136 Unit C — Market Research (ungated Sources Sought / Special Notice)
    // ────────────────────────────────────────────────────────────────────

    /// <summary>
    /// Returns ALL active "Sources Sought" and "Special Notice" notices matching the
    /// org's NAICS + certification profile. NOT score-ranked and NOT capped at top-N
    /// (a high cap / pagination guards against pathological result sizes). Applies the
    /// SAME set-aside cert rules as <see cref="GetRecommendedAsync"/>: a notice whose
    /// set-aside requires a cert the org lacks is skipped.
    /// </summary>
    public async Task<List<RecommendedOpportunityDto>> GetMarketResearchAsync(
        int orgId, int limit = 500, int? userId = null)
    {
        if (limit < 1) limit = 1;
        if (limit > 2000) limit = 2000;

        // 1. Org NAICS + certs (same as recommended)
        var naicsCodes = await _context.OrganizationNaics.AsNoTracking()
            .Where(n => n.OrganizationId == orgId)
            .Select(n => n.NaicsCode)
            .ToListAsync();

        if (naicsCodes.Count == 0)
        {
            _logger.LogInformation("Org {OrgId} has no NAICS codes — no market research notices", orgId);
            return [];
        }

        var orgCerts = await _context.OrganizationCertifications.AsNoTracking()
            .Where(c => c.OrganizationId == orgId && c.IsActive == "Y")
            .Select(c => c.CertificationType)
            .ToListAsync();
        var orgCertSet = orgCerts.ToHashSet(StringComparer.OrdinalIgnoreCase);

        // Phase 136 Unit G: include associated NAICS so market-research notices in
        // declared adjacent codes also surface.
        var associatedNaics = await _context.OrganizationAssociatedNaics.AsNoTracking()
            .Where(n => n.OrganizationId == orgId)
            .Select(n => n.NaicsCode)
            .ToListAsync();
        var candidateNaics = naicsCodes.Concat(associatedNaics).Distinct().ToList();

        // 2. Query active Sources Sought / Special Notice opportunities matching org NAICS (registered + associated).
        var now = DateTime.UtcNow;
        var candidates = await _context.Opportunities.AsNoTracking()
            .Where(o => candidateNaics.Contains(o.NaicsCode!)
                        && o.Active != "N"
                        && MarketResearchTypes.Contains(o.Type!)
                        && (o.ResponseDeadline == null || o.ResponseDeadline > now))
            .Select(o => new
            {
                o.NoticeId,
                o.Title,
                o.SolicitationNumber,
                o.DepartmentName,
                o.DepartmentCgac,
                o.SubTier,
                o.ContractingOfficeId,
                o.SetAsideCode,
                o.SetAsideDescription,
                o.NaicsCode,
                o.ClassificationCode,
                o.Type,
                o.EstimatedContractValue,
                o.AwardAmount,
                PostedDate = o.PostedDate,
                o.ResponseDeadline,
                o.PopState,
                o.PopCity,
                o.PopCountry,
                o.FhOrgId
            })
            .ToListAsync();

        // 2b. Exclude ignored opportunities
        if (userId.HasValue)
        {
            var ignoredIds = await _context.OpportunityIgnores
                .Where(i => i.UserId == userId.Value)
                .Select(i => i.NoticeId)
                .ToListAsync();
            if (ignoredIds.Count > 0)
            {
                var ignoredSet = ignoredIds.ToHashSet();
                candidates = candidates.Where(c => !ignoredSet.Contains(c.NoticeId)).ToList();
            }
        }

        // 3. Dedup: keep latest notice per solicitation (same rule as recommended)
        var deduped = candidates
            .GroupBy(c => string.IsNullOrEmpty(c.SolicitationNumber) ? c.NoticeId : c.SolicitationNumber)
            .Select(g => g.OrderByDescending(c => c.PostedDate).ThenByDescending(c => c.NoticeId).First())
            .ToList();

        // 4. Apply set-aside cert filtering (same rule as recommended) and build DTOs.
        // These notices are intentionally NOT scored — win-probability is irrelevant for
        // market research — so OqScore stays null and category is "MarketResearch".
        var result = new List<RecommendedOpportunityDto>();
        foreach (var c in deduped)
        {
            var setAsideCode = (c.SetAsideCode ?? "").Trim();
            if (!string.IsNullOrEmpty(setAsideCode)
                && SetAsideToCertType.TryGetValue(setAsideCode, out var requiredCert)
                && !orgCertSet.Contains(requiredCert))
            {
                continue;
            }

            int? daysRemaining = c.ResponseDeadline.HasValue
                ? Math.Max(0, (int)(c.ResponseDeadline.Value - now).TotalDays)
                : null;

            result.Add(new RecommendedOpportunityDto
            {
                NoticeId = c.NoticeId,
                Title = c.Title,
                SolicitationNumber = c.SolicitationNumber,
                DepartmentName = c.DepartmentName,
                SubTier = c.SubTier,
                ContractingOfficeId = c.ContractingOfficeId,
                SetAsideCode = c.SetAsideCode,
                SetAsideDescription = c.SetAsideDescription,
                NaicsCode = c.NaicsCode,
                ClassificationCode = c.ClassificationCode,
                NoticeType = c.Type,
                AwardAmount = c.AwardAmount,
                PostedDate = c.PostedDate.HasValue
                    ? c.PostedDate.Value.ToDateTime(TimeOnly.MinValue)
                    : null,
                ResponseDeadline = c.ResponseDeadline,
                DaysRemaining = daysRemaining,
                PopState = c.PopState,
                PopCity = c.PopCity,
                PopCountry = c.PopCountry,
                FhOrgId = c.FhOrgId,
                OqScore = null,
                OqScoreCategory = "MarketResearch",
                OqScoreFactors = [],
                Confidence = "Medium",
            });
        }

        // 5. Sort by most recently posted (most useful ordering for research) and cap.
        var ordered = result
            .OrderByDescending(r => r.PostedDate)
            .Take(limit)
            .ToList();

        // 6. Enrich with NAICS descriptions (batch lookup)
        var distinctNaics = ordered
            .Where(d => d.NaicsCode != null)
            .Select(d => d.NaicsCode!)
            .Distinct()
            .ToList();

        if (distinctNaics.Count > 0)
        {
            var naicsDescriptions = await _context.RefNaicsCodes.AsNoTracking()
                .Where(n => distinctNaics.Contains(n.NaicsCode))
                .ToDictionaryAsync(n => n.NaicsCode, n => n.Description);

            foreach (var dto in ordered)
            {
                if (dto.NaicsCode != null && naicsDescriptions.TryGetValue(dto.NaicsCode, out var desc))
                    dto.NaicsDescription = desc;
            }
        }

        _logger.LogInformation(
            "Market research: {Count} Sources Sought/Special Notice for org {OrgId} (from {Total} candidates)",
            ordered.Count, orgId, candidates.Count);

        return ordered;
    }

    // ────────────────────────────────────────────────────────────────────
    // Org context data (pre-loaded once per request)
    // ────────────────────────────────────────────────────────────────────

    private record OrgContext(
        decimal? AvgAwardValue,
        bool HasAwardData,
        HashSet<string> PastPerformanceNaics,
        HashSet<string> PastPerformanceAgencies,
        HashSet<string> AwardNaics,
        HashSet<string> AwardAgencies,
        HashSet<string> ExcludedUeis);

    /// <summary>
    /// Pre-loads all org-level context data needed by OQS factors in batch queries.
    /// </summary>
    private async Task<OrgContext> LoadOrgContextAsync(int orgId, List<string> orgNaicsCodes)
    {
        // Get org's entity UEIs
        var orgUeis = await _context.OrganizationEntities.AsNoTracking()
            .Where(oe => oe.OrganizationId == orgId && oe.IsActive == "Y")
            .Select(oe => oe.UeiSam)
            .ToListAsync();

        // Past award data from usaspending_award for value alignment + growth potential
        decimal? avgAwardValue = null;
        var hasAwardData = false;
        var awardNaics = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var awardAgencies = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        if (orgUeis.Count > 0)
        {
            var awardStats = await _context.UsaspendingAwards.AsNoTracking()
                .Where(a => a.RecipientUei != null && orgUeis.Contains(a.RecipientUei))
                .GroupBy(a => 1)
                .Select(g => new
                {
                    AvgValue = g.Average(a => a.TotalObligation),
                    Count = g.Count()
                })
                .FirstOrDefaultAsync();

            if (awardStats != null && awardStats.Count > 0)
            {
                avgAwardValue = awardStats.AvgValue;
                hasAwardData = true;
            }

            // Distinct NAICS and agencies from past awards
            var awardDimensions = await _context.UsaspendingAwards.AsNoTracking()
                .Where(a => a.RecipientUei != null && orgUeis.Contains(a.RecipientUei))
                .Select(a => new { a.NaicsCode, a.AwardingAgencyName })
                .Distinct()
                .ToListAsync();

            foreach (var ad in awardDimensions)
            {
                if (ad.NaicsCode != null) awardNaics.Add(ad.NaicsCode);
                if (ad.AwardingAgencyName != null) awardAgencies.Add(ad.AwardingAgencyName);
            }
        }

        // Past performance records
        var pastPerf = await _context.OrganizationPastPerformances.AsNoTracking()
            .Where(pp => pp.OrganizationId == orgId)
            .Select(pp => new { pp.NaicsCode, pp.AgencyName })
            .ToListAsync();

        var ppNaics = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var ppAgencies = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var pp in pastPerf)
        {
            if (pp.NaicsCode != null) ppNaics.Add(pp.NaicsCode);
            if (pp.AgencyName != null) ppAgencies.Add(pp.AgencyName);
        }

        // Excluded UEIs (for re-compete incumbent vulnerability check)
        // Get UEIs from exclusion records that are currently active
        var excludedUeis = await _context.SamExclusions.AsNoTracking()
            .Where(e => e.Uei != null)
            .Select(e => e.Uei!)
            .Distinct()
            .ToListAsync();

        return new OrgContext(
            avgAwardValue,
            hasAwardData,
            ppNaics,
            ppAgencies,
            awardNaics,
            awardAgencies,
            excludedUeis.ToHashSet(StringComparer.OrdinalIgnoreCase));
    }

    // ────────────────────────────────────────────────────────────────────
    // OQS Factor Scoring Methods
    // ────────────────────────────────────────────────────────────────────

    private record FactorResult(int Score, string Detail, bool HadRealData);

    /// <summary>
    /// Factor 1: Profile Match Strength (weight 0.20).
    /// Scores how well the opportunity matches org NAICS/certifications.
    /// </summary>
    private FactorResult ScoreProfileMatch(
        string? oppNaics, string setAsideCode,
        HashSet<string> primaryNaics, HashSet<string> orgCertSet,
        HashSet<string> associatedNaics)
    {
        if (string.IsNullOrEmpty(oppNaics))
            return new FactorResult(0, "No NAICS on opportunity", true);

        var isPrimary = primaryNaics.Contains(oppNaics);
        // Phase 136 Unit G: a self-declared "associated" NAICS (disjoint from the org's
        // registered NAICS) scores as a distinct tier just below a registered secondary
        // match. The exact weight is intentionally conservative and tunable (Open Question #4).
        var isAssociated = associatedNaics.Contains(oppNaics);
        string? reqCert = null;
        var needsCert = !string.IsNullOrEmpty(setAsideCode)
                        && SetAsideToCertType.TryGetValue(setAsideCode, out reqCert);
        var hasCert = needsCert && reqCert != null && orgCertSet.Contains(reqCert);
        var noCertNeeded = string.IsNullOrEmpty(setAsideCode)
                          || !SetAsideToCertType.ContainsKey(setAsideCode);

        if (isPrimary && (hasCert || noCertNeeded))
            return new FactorResult(100, "Primary NAICS + cert match", true);

        if (isPrimary && !hasCert && orgCertSet.Count > 0)
            return new FactorResult(80, "Primary NAICS + related cert", true);

        if (isAssociated && (hasCert || noCertNeeded))
            return new FactorResult(50, "Associated NAICS match (declared)", true);

        if (isAssociated && needsCert && !hasCert)
            return new FactorResult(30, "Associated NAICS, wrong cert", true);

        if (!isPrimary && (hasCert || noCertNeeded))
            return new FactorResult(60, "Secondary NAICS match", true);

        if (!isPrimary && needsCert && !hasCert)
            return new FactorResult(30, "NAICS match but wrong cert", true);

        return new FactorResult(0, "No match", true);
    }

    /// <summary>
    /// Factor 2: Estimated Value Alignment (weight 0.15).
    /// Scores how well the contract size fits the org's typical award range.
    /// </summary>
    private static FactorResult ScoreValueAlignment(decimal? oppValue, decimal? avgAwardValue, bool hasAwardData)
    {
        if (!hasAwardData)
            return new FactorResult(50, "No past award data for comparison", false);

        if (!oppValue.HasValue || oppValue.Value <= 0)
            return new FactorResult(50, "No estimated value on opportunity", false);

        if (!avgAwardValue.HasValue || avgAwardValue.Value <= 0)
            return new FactorResult(50, "Avg award value unavailable", false);

        var ratio = oppValue.Value / avgAwardValue.Value;

        if (ratio >= 0.5m && ratio <= 2.0m)
            return new FactorResult(100, $"Value within sweet spot (ratio {ratio:F1}x)", true);
        if (ratio >= 0.25m && ratio <= 4.0m)
            return new FactorResult(70, $"Value within reasonable range (ratio {ratio:F1}x)", true);
        if (ratio >= 0.1m && ratio <= 10.0m)
            return new FactorResult(40, $"Value stretch range (ratio {ratio:F1}x)", true);

        return new FactorResult(20, $"Value outside typical range (ratio {ratio:F1}x)", true);
    }

    /// <summary>
    /// Factor 3: Competition Level (weight 0.10).
    /// Fewer known competitors = better opportunity.
    /// </summary>
    private static FactorResult ScoreCompetition(int vendorCount)
    {
        if (vendorCount <= 0)
            return new FactorResult(50, "No competition data available", false);

        if (vendorCount <= 3)
            return new FactorResult(100, $"{vendorCount} known competitors", true);

        // Exponential decay: score = 100 * e^(-0.15 * (count - 1)), min 10
        var score = (int)Math.Max(10, 100 * Math.Exp(-0.15 * (vendorCount - 1)));
        return new FactorResult(score, $"{vendorCount} known competitors", true);
    }

    /// <summary>
    /// Factor 4: Timeline Feasibility (weight 0.15).
    /// Smooth curve based on days remaining to respond.
    /// </summary>
    private static FactorResult ScoreTimeline(int? daysRemaining)
    {
        if (!daysRemaining.HasValue)
            return new FactorResult(50, "No response deadline", false);

        if (daysRemaining.Value <= 0)
            return new FactorResult(0, "Past deadline", true);

        // Smooth curve: days / 45 * 100, clamped to [0, 100]
        var score = (int)Math.Min(100, Math.Round((double)daysRemaining.Value / 45.0 * 100.0));
        return new FactorResult(score, $"{daysRemaining.Value} days remaining", true);
    }

    /// <summary>
    /// Factor 5: Reuse Potential (weight 0.10).
    /// Can the org reuse existing past performance for this opportunity?
    /// </summary>
    private static FactorResult ScoreReusePotential(string? oppNaics, string? oppAgency, OrgContext ctx)
    {
        if (ctx.PastPerformanceNaics.Count == 0 && ctx.PastPerformanceAgencies.Count == 0)
            return new FactorResult(0, "No past performance records", false);

        var naicsMatch = !string.IsNullOrEmpty(oppNaics) && ctx.PastPerformanceNaics.Contains(oppNaics);
        var agencyMatch = !string.IsNullOrEmpty(oppAgency) && ctx.PastPerformanceAgencies.Contains(oppAgency);

        if (naicsMatch && agencyMatch)
            return new FactorResult(100, "Past performance in same NAICS + agency", true);
        if (naicsMatch)
            return new FactorResult(60, "Past performance in same NAICS", true);
        if (agencyMatch)
            return new FactorResult(40, "Past performance at same agency", true);

        return new FactorResult(10, "No matching past performance", true);
    }

    /// <summary>
    /// Factor 6: Growth Potential (weight 0.15).
    /// New territory (agency/NAICS) = higher growth score.
    /// </summary>
    private static FactorResult ScoreGrowthPotential(string? oppNaics, string? oppAgency, OrgContext ctx)
    {
        if (!ctx.HasAwardData)
            return new FactorResult(50, "No past award data for growth analysis", false);

        var hasNaicsHistory = !string.IsNullOrEmpty(oppNaics) && ctx.AwardNaics.Contains(oppNaics);
        var hasAgencyHistory = !string.IsNullOrEmpty(oppAgency) && ctx.AwardAgencies.Contains(oppAgency);

        if (!hasAgencyHistory && !hasNaicsHistory)
            return new FactorResult(80, "New agency + new NAICS — high growth potential", true);
        if (!hasAgencyHistory)
            return new FactorResult(80, "New agency — high growth potential", true);
        if (!hasNaicsHistory)
            return new FactorResult(60, "New NAICS — moderate growth potential", true);

        return new FactorResult(20, "Known market — low growth potential", true);
    }

    /// <summary>
    /// Factor 7: Re-compete Advantage (weight 0.15).
    /// Scores whether a re-compete has a vulnerable incumbent.
    /// </summary>
    private FactorResult ScoreRecompeteAdvantage(bool isRecompete, string? incumbentName, OrgContext ctx)
    {
        if (!isRecompete)
            return new FactorResult(60, "New requirement (not a re-compete)", true);

        if (string.IsNullOrEmpty(incumbentName))
            return new FactorResult(50, "Re-compete but no incumbent data", false);

        // Check incumbent vulnerability: is the incumbent excluded in SAM?
        // We check by name match against exclusion records (UEI-based check via entity lookup)
        // For now, check if any excluded UEI matches known vendors
        // A more robust check would look up the incumbent's UEI, but we don't have that mapping directly
        // So we default to a moderate score for re-competes with known incumbents
        return new FactorResult(50, $"Re-compete, incumbent: {incumbentName}", true);
    }

    // ────────────────────────────────────────────────────────────────────
    // Helpers
    // ────────────────────────────────────────────────────────────────────

    /// <summary>
    /// Phase 136 Unit D — renormalized OQS over real-data factors only.
    /// Computes the weighted score using ONLY factors where HadRealData is true,
    /// dividing by the SUM of those factors' weights so the present weights total 1.0.
    /// Returns null when ZERO factors had real data (caller must surface
    /// "insufficient data" rather than a misleading 0).
    /// </summary>
    private static decimal? ComputeRenormalizedScore(IReadOnlyList<OqScoreFactorDto> factors)
    {
        var presentWeight = factors.Where(f => f.HadRealData).Sum(f => f.Weight);
        if (presentWeight <= 0m)
            return null;

        // f.Score is the raw 0-100 factor score; renormalize so present weights sum to 1.0.
        var weighted = factors.Where(f => f.HadRealData).Sum(f => f.Score * f.Weight);
        return Math.Round(weighted / presentWeight, 1);
    }

    /// <summary>Maps a (possibly null) OQS to its category label.</summary>
    private static string CategoryFor(decimal? oqScore) => oqScore switch
    {
        null => "InsufficientData",
        >= 70 => "High",
        >= 40 => "Medium",
        >= 15 => "Low",
        _ => "VeryLow"
    };

    /// <summary>
    /// Builds an OqScoreFactorDto with calculated weighted score.
    /// </summary>
    private static OqScoreFactorDto BuildFactor(string name, int score, decimal weight, string detail, bool hadRealData)
    {
        return new OqScoreFactorDto
        {
            Name = name,
            Score = score,
            Weight = weight,
            WeightedScore = Math.Round(score * weight, 1),
            Detail = detail,
            HadRealData = hadRealData,
        };
    }
}
