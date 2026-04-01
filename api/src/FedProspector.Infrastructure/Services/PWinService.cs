using FedProspector.Core.DTOs.Intelligence;
using FedProspector.Core.Interfaces;
using FedProspector.Infrastructure.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;

namespace FedProspector.Infrastructure.Services;

public class PWinService : IPWinService
{
    private readonly FedProspectorDbContext _context;
    private readonly IOrganizationEntityService _orgEntityService;
    private readonly ILogger<PWinService> _logger;

    /// <summary>
    /// Maps set-aside codes to the certification types they require.
    /// </summary>
    private static readonly Dictionary<string, string[]> SetAsideCertMap = new(StringComparer.OrdinalIgnoreCase)
    {
        ["WOSB"] = ["WOSB", "EDWOSB"],
        ["WOSBSS"] = ["WOSB", "EDWOSB"],
        ["EDWOSB"] = ["EDWOSB"],
        ["EDWOSBSS"] = ["EDWOSB"],
        ["8A"] = ["8(a)"],
        ["8AN"] = ["8(a)"],
        ["SBA"] = ["8(a)", "WOSB", "EDWOSB", "HUBZone", "SDVOSB"],
        ["SBP"] = ["8(a)", "WOSB", "EDWOSB", "HUBZone", "SDVOSB"],
        ["HZC"] = ["HUBZone"],
        ["HZS"] = ["HUBZone"],
        ["SDVOSBC"] = ["SDVOSB", "VOSB"],
        ["SDVOSBS"] = ["SDVOSB", "VOSB"],
    };

    public PWinService(FedProspectorDbContext context, IOrganizationEntityService orgEntityService, ILogger<PWinService> logger)
    {
        _context = context;
        _orgEntityService = orgEntityService;
        _logger = logger;
    }

    public async Task<PWinResultDto> CalculateAsync(string noticeId, int orgId)
    {
        var opp = await _context.Opportunities.AsNoTracking()
            .FirstOrDefaultAsync(o => o.NoticeId == noticeId)
            ?? throw new KeyNotFoundException($"Opportunity {noticeId} not found");

        var org = await _context.Organizations.AsNoTracking()
            .FirstOrDefaultAsync(o => o.OrganizationId == orgId)
            ?? throw new KeyNotFoundException($"Organization {orgId} not found");

        var orgCerts = await _context.OrganizationCertifications.AsNoTracking()
            .Where(c => c.OrganizationId == orgId && c.IsActive == "Y")
            .Select(c => c.CertificationType)
            .ToListAsync();

        var linkedUeis = await _orgEntityService.GetLinkedUeisAsync(orgId);
        if (!string.IsNullOrEmpty(org.UeiSam) && !linkedUeis.Contains(org.UeiSam))
            linkedUeis.Add(org.UeiSam);

        var prospect = await _context.Prospects
            .FirstOrDefaultAsync(p => p.NoticeId == noticeId && p.OrganizationId == orgId);

        var competitionCache = new Dictionary<string, PWinFactorDto>();
        var naicsExpCache = new Dictionary<string, NaicsExperienceData>();

        var result = await CalculateWithContextAsync(
            opp, org, orgCerts, linkedUeis, competitionCache, naicsExpCache, prospect);

        if (prospect != null)
            await _context.SaveChangesAsync();

        return result;
    }

    public async Task<BatchPWinResponse> CalculateBatchAsync(BatchPWinRequest request, int orgId)
    {
        if (request.NoticeIds.Count > 25)
            throw new ArgumentException("Batch pWin requests are limited to 25 notice IDs.");

        // Pre-load shared org data once for the entire batch
        var org = await _context.Organizations.AsNoTracking()
            .FirstOrDefaultAsync(o => o.OrganizationId == orgId)
            ?? throw new KeyNotFoundException($"Organization {orgId} not found");

        var orgCerts = await _context.OrganizationCertifications.AsNoTracking()
            .Where(c => c.OrganizationId == orgId && c.IsActive == "Y")
            .Select(c => c.CertificationType)
            .ToListAsync();

        var linkedUeis = await _orgEntityService.GetLinkedUeisAsync(orgId);
        if (!string.IsNullOrEmpty(org.UeiSam) && !linkedUeis.Contains(org.UeiSam))
            linkedUeis.Add(org.UeiSam);

        // Pre-load all opportunities in one query
        var opportunities = await _context.Opportunities.AsNoTracking()
            .Where(o => request.NoticeIds.Contains(o.NoticeId))
            .ToDictionaryAsync(o => o.NoticeId);

        // Pre-load all prospects for the batch in one query
        var prospects = await _context.Prospects
            .Where(p => request.NoticeIds.Contains(p.NoticeId) && p.OrganizationId == orgId)
            .ToDictionaryAsync(p => p.NoticeId);

        // Caches shared across all opportunities in the batch
        var competitionCache = new Dictionary<string, PWinFactorDto>();
        var naicsExpCache = new Dictionary<string, NaicsExperienceData>();

        var results = new Dictionary<string, BatchPWinEntry?>();

        foreach (var noticeId in request.NoticeIds)
        {
            try
            {
                if (!opportunities.TryGetValue(noticeId, out var opp))
                    throw new KeyNotFoundException($"Opportunity {noticeId} not found");

                prospects.TryGetValue(noticeId, out var prospect);

                var result = await CalculateWithContextAsync(
                    opp, org, orgCerts, linkedUeis, competitionCache, naicsExpCache, prospect);

                results[noticeId] = new BatchPWinEntry
                {
                    Score = result.Score,
                    Category = result.Category
                };
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "Batch pWin calculation failed for {NoticeId}", noticeId);
                results[noticeId] = null;
            }
        }

        // Batch save all prospect updates at once
        await _context.SaveChangesAsync();

        return new BatchPWinResponse { Results = results };
    }

    /// <summary>
    /// Cached NAICS experience data: pre-queried past performance and FPDS records for a NAICS code.
    /// </summary>
    private sealed record NaicsExperienceData(
        int TotalContracts,
        List<(DateTime? PeriodEnd, string? AgencyName, decimal? ContractValue)> PpRecords,
        List<(DateOnly? DateSigned, string? AgencyName, decimal? Value)> FpdsRecords);

    /// <summary>
    /// Core pWin calculation that uses pre-loaded context to avoid redundant queries.
    /// Competition and NAICS experience results are cached per NAICS code.
    /// </summary>
    private async Task<PWinResultDto> CalculateWithContextAsync(
        Core.Models.Opportunity opp,
        Core.Models.Organization org,
        List<string> orgCerts,
        List<string> linkedUeis,
        Dictionary<string, PWinFactorDto> competitionCache,
        Dictionary<string, NaicsExperienceData> naicsExpCache,
        Core.Models.Prospect? prospect)
    {
        var factors = new List<PWinFactorDto>();
        var suggestions = new List<string>();

        // 1. Set-aside match (weight 0.20)
        factors.Add(ScoreSetAsideMatch(opp.SetAsideCode, orgCerts, suggestions));

        // 2. NAICS experience with past performance relevance (weight 0.20) — uses cached data
        factors.Add(await ScoreNaicsExperienceCachedAsync(opp, org.OrganizationId, linkedUeis, naicsExpCache, suggestions));

        // 3. Competition level (weight 0.15) — uses cached data
        factors.Add(await ScoreCompetitionLevelCachedAsync(opp.NaicsCode, competitionCache));

        // 4. Incumbent advantage with vulnerability signals (weight 0.15) — per-opportunity
        factors.Add(await ScoreIncumbentAdvantageAsync(opp, linkedUeis, suggestions));

        // 5. Teaming strength (weight 0.10) — per-opportunity (depends on opp NAICS)
        factors.Add(await ScoreTeamingStrengthAsync(linkedUeis, opp.NaicsCode));

        // 6. Time to respond (weight 0.10) — pure computation
        factors.Add(ScoreTimeToRespond(opp.ResponseDeadline, suggestions));

        // 7. Contract value fit (weight 0.10) — per-opportunity
        factors.Add(await ScoreContractValueFitAsync(opp.EstimatedContractValue, org.OrganizationId, linkedUeis));

        var totalScore = Math.Round(factors.Sum(f => f.WeightedScore), 1);

        var category = totalScore switch
        {
            >= 70 => "High",
            >= 40 => "Medium",
            >= 15 => "Low",
            _ => "VeryLow"
        };

        var realDataCount = factors.Count(f => f.HadRealData);
        var dataCompletenessPercent = (int)Math.Round(100.0 * realDataCount / factors.Count);
        var confidence = realDataCount >= 6 ? "High" : realDataCount >= 4 ? "Medium" : "Low";

        int? prospectId = prospect?.ProspectId;
        if (prospect != null)
        {
            prospect.WinProbability = (decimal)totalScore;
            prospect.UpdatedAt = DateTime.UtcNow;
        }

        _logger.LogInformation("pWin calculated for opportunity {NoticeId}, org {OrgId}: {Score}% ({Category}, confidence={Confidence})",
            opp.NoticeId, org.OrganizationId, totalScore, category, confidence);

        return new PWinResultDto
        {
            ProspectId = prospectId,
            NoticeId = opp.NoticeId,
            Score = totalScore,
            Category = category,
            Confidence = confidence,
            DataCompletenessPercent = dataCompletenessPercent,
            Factors = factors,
            Suggestions = suggestions
        };
    }

    /// <summary>
    /// Wrapper around ScoreCompetitionLevelAsync that caches results per NAICS code.
    /// </summary>
    private async Task<PWinFactorDto> ScoreCompetitionLevelCachedAsync(
        string? naicsCode, Dictionary<string, PWinFactorDto> cache)
    {
        var key = naicsCode ?? "";
        if (cache.TryGetValue(key, out var cached))
            return cached;

        var result = await ScoreCompetitionLevelAsync(naicsCode);
        cache[key] = result;
        return result;
    }

    /// <summary>
    /// Wrapper around ScoreNaicsExperienceAsync that caches the DB query results per NAICS code,
    /// then computes opportunity-specific bonuses (agency match, value similarity) from the cached data.
    /// </summary>
    private async Task<PWinFactorDto> ScoreNaicsExperienceCachedAsync(
        Core.Models.Opportunity opp, int orgId, List<string> linkedUeis,
        Dictionary<string, NaicsExperienceData> cache, List<string> suggestions)
    {
        const decimal weight = 0.20m;
        var naicsCode = opp.NaicsCode;

        if (string.IsNullOrEmpty(naicsCode))
        {
            return MakeFactor("NAICS Experience", 50, weight, "No NAICS code on opportunity", hadRealData: false);
        }

        // Load and cache the NAICS-specific DB data
        if (!cache.TryGetValue(naicsCode, out var data))
        {
            var ppRecords = await _context.OrganizationPastPerformances.AsNoTracking()
                .Where(p => p.OrganizationId == orgId && p.NaicsCode == naicsCode)
                .Select(p => new { p.PeriodEnd, p.AgencyName, p.ContractValue })
                .ToListAsync();

            var fpdsRecords = new List<(DateOnly? DateSigned, string? AgencyName, decimal? Value)>();
            if (linkedUeis.Count > 0)
            {
                var fpdsRaw = await _context.FpdsContracts.AsNoTracking()
                    .Where(c => c.VendorUei != null && linkedUeis.Contains(c.VendorUei) && c.NaicsCode == naicsCode)
                    .Select(c => new { c.ContractId, c.DateSigned, c.AgencyName, c.BaseAndAllOptions })
                    .Distinct()
                    .Take(200)
                    .ToListAsync();

                fpdsRecords = fpdsRaw
                    .Select(c => (c.DateSigned, c.AgencyName, c.BaseAndAllOptions))
                    .ToList();
            }

            data = new NaicsExperienceData(
                ppRecords.Count + fpdsRecords.Count,
                ppRecords.Select(p => (p.PeriodEnd, p.AgencyName, p.ContractValue)).ToList(),
                fpdsRecords);
            cache[naicsCode] = data;
        }

        // Score using cached data (same logic as original ScoreNaicsExperienceAsync)
        if (data.TotalContracts == 0)
        {
            suggestions.Add($"Limited past performance in NAICS {naicsCode}. Consider teaming with experienced partners.");
            return MakeFactor("NAICS Experience", 10, weight,
                $"No past performance found in NAICS {naicsCode}", hadRealData: false);
        }

        var baseScore = Math.Min(100.0, 20.0 + 16.0 * data.TotalContracts);

        var now = DateTime.UtcNow;
        double recencySum = 0;
        double recencyMax = 0;

        foreach (var pp in data.PpRecords)
        {
            recencyMax += 1.0;
            recencySum += RecencyWeight(pp.PeriodEnd, now);
        }
        foreach (var fpds in data.FpdsRecords)
        {
            recencyMax += 1.0;
            var dt = fpds.DateSigned.HasValue ? fpds.DateSigned.Value.ToDateTime(TimeOnly.MinValue) : (DateTime?)null;
            recencySum += RecencyWeight(dt, now);
        }

        var recencyFactor = recencyMax > 0 ? recencySum / recencyMax : 0.5;

        double agencyBonus = 0;
        var oppAgency = opp.DepartmentName?.Trim();
        if (!string.IsNullOrEmpty(oppAgency))
        {
            var hasAgencyMatch = data.PpRecords.Any(p =>
                    !string.IsNullOrEmpty(p.AgencyName) &&
                    p.AgencyName.Contains(oppAgency, StringComparison.OrdinalIgnoreCase))
                || data.FpdsRecords.Any(f =>
                    !string.IsNullOrEmpty(f.AgencyName) &&
                    f.AgencyName.Contains(oppAgency, StringComparison.OrdinalIgnoreCase));
            if (hasAgencyMatch)
                agencyBonus = 10;
        }

        double valueSimilarityBonus = 0;
        if (opp.EstimatedContractValue.HasValue && opp.EstimatedContractValue.Value > 0)
        {
            var oppVal = (double)opp.EstimatedContractValue.Value;
            var allValues = data.PpRecords
                .Where(p => p.ContractValue.HasValue && p.ContractValue.Value > 0)
                .Select(p => (double)p.ContractValue!.Value)
                .Concat(data.FpdsRecords
                    .Where(f => f.Value.HasValue && f.Value.Value > 0)
                    .Select(f => (double)f.Value!.Value));

            if (allValues.Any(v =>
            {
                var ratio = v > oppVal ? v / oppVal : oppVal / v;
                return ratio <= 2.0;
            }))
            {
                valueSimilarityBonus = 5;
            }
        }

        var finalScore = (decimal)Math.Clamp(baseScore * recencyFactor + agencyBonus + valueSimilarityBonus, 10.0, 100.0);
        finalScore = Math.Round(finalScore, 1);

        var detail = $"NAICS {naicsCode}: {data.TotalContracts} contract(s), recency={recencyFactor:P0}";
        if (agencyBonus > 0) detail += ", agency match";
        if (valueSimilarityBonus > 0) detail += ", value fit";

        return MakeFactor("NAICS Experience", finalScore, weight, detail);
    }

    // -----------------------------------------------------------------------
    // Factor 1: Set-Aside Match (weight 0.20)
    // -----------------------------------------------------------------------

    private static PWinFactorDto ScoreSetAsideMatch(string? setAsideCode, List<string> orgCerts, List<string> suggestions)
    {
        const decimal weight = 0.20m;
        var code = (setAsideCode ?? "").Trim();

        decimal score;
        string detail;
        bool hadRealData = true;

        if (string.IsNullOrEmpty(code))
        {
            score = 50;
            detail = "Full and open competition (no set-aside)";
            hadRealData = false; // No set-aside code to evaluate
        }
        else if (SetAsideCertMap.TryGetValue(code, out var requiredCerts))
        {
            var hasExact = orgCerts.Any(c => requiredCerts.Contains(c, StringComparer.OrdinalIgnoreCase));
            if (hasExact)
            {
                score = 100;
                detail = $"Organization holds required certification for {code} set-aside";
            }
            else
            {
                // Check if org has any related small business certification
                var hasRelated = orgCerts.Any(c =>
                    SetAsideCertMap.Values.SelectMany(v => v).Contains(c, StringComparer.OrdinalIgnoreCase));
                if (hasRelated)
                {
                    score = 50;
                    detail = $"Organization has related certifications but not exact match for {code}";
                }
                else
                {
                    score = 0;
                    detail = $"Organization lacks required certification for {code} set-aside";
                    suggestions.Add($"Your organization lacks the required certification for this {code} set-aside.");
                }
            }
        }
        else
        {
            // Unknown set-aside code; be neutral
            score = 50;
            detail = $"Set-aside type {code} — unable to match against org certifications";
            hadRealData = false;
        }

        return MakeFactor("Set-Aside Match", score, weight, detail, hadRealData);
    }

    // -----------------------------------------------------------------------
    // Factor 2: NAICS Experience / Past Performance Relevance (weight 0.20)
    // Uses continuous curve with recency weighting, agency match, and value similarity.
    // -----------------------------------------------------------------------

    /// <summary>
    /// Scores NAICS experience using a continuous curve with bonuses for recency,
    /// agency match, and contract value similarity to the opportunity.
    /// </summary>
    private async Task<PWinFactorDto> ScoreNaicsExperienceAsync(
        Core.Models.Opportunity opp, int orgId, List<string> linkedUeis, List<string> suggestions)
    {
        const decimal weight = 0.20m;
        var naicsCode = opp.NaicsCode;

        if (string.IsNullOrEmpty(naicsCode))
        {
            return MakeFactor("NAICS Experience", 50, weight, "No NAICS code on opportunity", hadRealData: false);
        }

        // Gather past performance records for this NAICS
        var ppRecords = await _context.OrganizationPastPerformances.AsNoTracking()
            .Where(p => p.OrganizationId == orgId && p.NaicsCode == naicsCode)
            .Select(p => new { p.PeriodEnd, p.AgencyName, p.ContractValue })
            .ToListAsync();

        // Gather FPDS contracts where any linked entity is vendor in this NAICS
        var fpdsRecords = new List<(DateOnly? dateSigned, string? agencyName, decimal? value)>();
        if (linkedUeis.Count > 0)
        {
            var fpdsRaw = await _context.FpdsContracts.AsNoTracking()
                .Where(c => c.VendorUei != null && linkedUeis.Contains(c.VendorUei) && c.NaicsCode == naicsCode)
                .Select(c => new { c.ContractId, c.DateSigned, c.AgencyName, c.BaseAndAllOptions })
                .Distinct()
                .Take(200)
                .ToListAsync();

            fpdsRecords = fpdsRaw
                .Select(c => (c.DateSigned, c.AgencyName, c.BaseAndAllOptions))
                .ToList();
        }

        var totalContracts = ppRecords.Count + fpdsRecords.Count;
        if (totalContracts == 0)
        {
            suggestions.Add($"Limited past performance in NAICS {naicsCode}. Consider teaming with experienced partners.");
            return MakeFactor("NAICS Experience", 10, weight,
                $"No past performance found in NAICS {naicsCode}", hadRealData: false);
        }

        // Base score: continuous curve — score = min(100, 20 + 16 * count), clamped to [10, 100]
        var baseScore = Math.Min(100.0, 20.0 + 16.0 * totalContracts);

        // Recency bonus: contracts in last 2 years get full weight, 2-5 years get 0.5x, >5 years get 0.25x
        var now = DateTime.UtcNow;
        double recencySum = 0;
        double recencyMax = 0; // max possible if all were recent

        foreach (var pp in ppRecords)
        {
            recencyMax += 1.0;
            recencySum += RecencyWeight(pp.PeriodEnd, now);
        }
        foreach (var fpds in fpdsRecords)
        {
            recencyMax += 1.0;
            var dt = fpds.dateSigned.HasValue ? fpds.dateSigned.Value.ToDateTime(TimeOnly.MinValue) : (DateTime?)null;
            recencySum += RecencyWeight(dt, now);
        }

        // Recency factor: ratio of weighted sum to max possible (1.0 if all recent)
        var recencyFactor = recencyMax > 0 ? recencySum / recencyMax : 0.5;

        // Agency match bonus: +10 if any past contract was at the same agency
        double agencyBonus = 0;
        var oppAgency = opp.DepartmentName?.Trim();
        if (!string.IsNullOrEmpty(oppAgency))
        {
            var hasAgencyMatch = ppRecords.Any(p =>
                    !string.IsNullOrEmpty(p.AgencyName) &&
                    p.AgencyName.Contains(oppAgency, StringComparison.OrdinalIgnoreCase))
                || fpdsRecords.Any(f =>
                    !string.IsNullOrEmpty(f.agencyName) &&
                    f.agencyName.Contains(oppAgency, StringComparison.OrdinalIgnoreCase));
            if (hasAgencyMatch)
                agencyBonus = 10;
        }

        // Value similarity bonus: +5 if any past contract is within 2x of opportunity value
        double valueSimilarityBonus = 0;
        if (opp.EstimatedContractValue.HasValue && opp.EstimatedContractValue.Value > 0)
        {
            var oppVal = (double)opp.EstimatedContractValue.Value;
            var allValues = ppRecords
                .Where(p => p.ContractValue.HasValue && p.ContractValue.Value > 0)
                .Select(p => (double)p.ContractValue!.Value)
                .Concat(fpdsRecords
                    .Where(f => f.value.HasValue && f.value.Value > 0)
                    .Select(f => (double)f.value!.Value));

            if (allValues.Any(v =>
            {
                var ratio = v > oppVal ? v / oppVal : oppVal / v;
                return ratio <= 2.0;
            }))
            {
                valueSimilarityBonus = 5;
            }
        }

        // Final score: base * recencyFactor + bonuses, clamped to [10, 100]
        var finalScore = (decimal)Math.Clamp(baseScore * recencyFactor + agencyBonus + valueSimilarityBonus, 10.0, 100.0);
        finalScore = Math.Round(finalScore, 1);

        var detail = $"NAICS {naicsCode}: {totalContracts} contract(s), recency={recencyFactor:P0}";
        if (agencyBonus > 0) detail += ", agency match";
        if (valueSimilarityBonus > 0) detail += ", value fit";

        return MakeFactor("NAICS Experience", finalScore, weight, detail);
    }

    /// <summary>
    /// Returns a recency weight for a contract date: 1.0 for &lt;2 years, 0.5 for 2-5 years, 0.25 for older.
    /// </summary>
    private static double RecencyWeight(DateTime? endDate, DateTime now)
    {
        if (!endDate.HasValue) return 0.25; // Unknown date gets minimal weight
        var yearsAgo = (now - endDate.Value).TotalDays / 365.25;
        return yearsAgo switch
        {
            <= 2 => 1.0,
            <= 5 => 0.5,
            _ => 0.25
        };
    }

    // -----------------------------------------------------------------------
    // Factor 3: Competition Level (weight 0.15)
    // Uses percentile-based relative scoring against all NAICS codes.
    // -----------------------------------------------------------------------

    /// <summary>
    /// Cache for the NAICS vendor count distribution, populated on first call per service lifetime.
    /// </summary>
    private List<int>? _naicsDistributionCache;

    /// <summary>
    /// Scores competition level using percentile ranking: where does this NAICS fall
    /// in the overall distribution of vendor counts across all NAICS codes?
    /// </summary>
    private async Task<PWinFactorDto> ScoreCompetitionLevelAsync(string? naicsCode)
    {
        const decimal weight = 0.15m;

        if (string.IsNullOrEmpty(naicsCode))
        {
            return MakeFactor("Competition Level", 50, weight, "No NAICS code — competition level unknown", hadRealData: false);
        }

        // Get vendor count for this NAICS from the NAICS-level summary row (agency_name = '*')
        var naicsVendorCount = await _context.UsaspendingAwardSummaries.AsNoTracking()
            .Where(s => s.NaicsCode == naicsCode && s.AgencyName == "*")
            .Select(s => s.VendorCount)
            .FirstOrDefaultAsync();

        if (naicsVendorCount == 0)
        {
            // Fallback to FPDS if no summary data
            var threeYearsAgo = DateOnly.FromDateTime(DateTime.UtcNow.AddYears(-3));
            naicsVendorCount = await _context.FpdsContracts.AsNoTracking()
                .Where(c => c.NaicsCode == naicsCode
                            && c.DateSigned != null
                            && c.DateSigned >= threeYearsAgo
                            && c.VendorUei != null)
                .Select(c => c.VendorUei)
                .Distinct()
                .CountAsync();
        }

        if (naicsVendorCount == 0)
        {
            return MakeFactor("Competition Level", 50, weight,
                $"No competition data for NAICS {naicsCode}", hadRealData: false);
        }

        // Get the distribution across all NAICS codes for percentile scoring (cached)
        _naicsDistributionCache ??= await _context.UsaspendingAwardSummaries.AsNoTracking()
            .Where(s => s.AgencyName == "*")
            .Select(s => s.VendorCount)
            .ToListAsync();

        if (_naicsDistributionCache.Count == 0)
        {
            // Fallback to absolute scoring if no distribution data
            var rawScore = 100.0 * Math.Exp(-0.15 * (naicsVendorCount - 1));
            var fallbackScore = (decimal)Math.Clamp(rawScore, 10.0, 100.0);
            return MakeFactor("Competition Level", Math.Round(fallbackScore, 1), weight,
                $"{naicsVendorCount} vendors in NAICS {naicsCode}");
        }

        // Calculate percentile: what % of NAICS codes have MORE vendors than this one?
        // Higher percentile (fewer have more) = MORE competitive = LOWER score
        var countWithMore = _naicsDistributionCache.Count(c => c > naicsVendorCount);
        var percentile = (double)countWithMore / _naicsDistributionCache.Count * 100.0;

        // Convert percentile to score:
        // If 90% of NAICS have more vendors → this NAICS has LOW competition → score 90
        // If 10% of NAICS have more vendors → this NAICS has HIGH competition → score 10
        var score = (decimal)Math.Clamp(percentile, 5.0, 95.0);
        score = Math.Round(score, 1);

        var detail = $"{naicsVendorCount} vendors in NAICS {naicsCode} — " +
                     $"less competitive than {percentile:F0}% of NAICS codes";

        return MakeFactor("Competition Level", score, weight, detail);
    }

    // -----------------------------------------------------------------------
    // Factor 4: Incumbent Advantage with vulnerability signals (weight 0.15)
    // -----------------------------------------------------------------------

    /// <summary>
    /// Scores incumbent advantage. When an incumbent is found and is not us,
    /// checks for vulnerability signals (SAM expiring, exclusions, over-spending)
    /// that may indicate the incumbent is beatable.
    /// </summary>
    private async Task<PWinFactorDto> ScoreIncumbentAdvantageAsync(
        Core.Models.Opportunity opp, List<string> linkedUeis, List<string> suggestions)
    {
        const decimal weight = 0.15m;

        // Check if opportunity has incumbent info directly
        var incumbentUei = opp.IncumbentUei;
        var incumbentName = opp.IncumbentName;

        // Also try to find incumbent via solicitation number in FPDS
        if (string.IsNullOrEmpty(incumbentUei) && !string.IsNullOrEmpty(opp.SolicitationNumber))
        {
            var priorContract = await _context.FpdsContracts.AsNoTracking()
                .Where(c => c.SolicitationNumber == opp.SolicitationNumber)
                .OrderByDescending(c => c.DateSigned)
                .FirstOrDefaultAsync();

            if (priorContract != null)
            {
                incumbentUei = priorContract.VendorUei;
                incumbentName = priorContract.VendorName;
            }
        }

        // Also check Document Intelligence attachment summaries for recompete/incumbent data
        if (string.IsNullOrEmpty(incumbentUei))
        {
            var intelSummary = await _context.OpportunityAttachmentSummaries.AsNoTracking()
                .Where(s => s.NoticeId == opp.NoticeId && s.IncumbentName != null)
                .OrderByDescending(s => s.ExtractedAt)
                .Select(s => new { s.IncumbentName, s.IsRecompete })
                .FirstOrDefaultAsync();

            if (intelSummary != null)
            {
                incumbentName = intelSummary.IncumbentName;
                // We don't have UEI from intel, but we have a name — try to find the entity
                if (!string.IsNullOrEmpty(incumbentName))
                {
                    var matchedEntity = await _context.Entities.AsNoTracking()
                        .Where(e => e.LegalBusinessName != null && e.LegalBusinessName == incumbentName)
                        .Select(e => e.UeiSam)
                        .FirstOrDefaultAsync();
                    if (!string.IsNullOrEmpty(matchedEntity))
                        incumbentUei = matchedEntity;
                }
            }

            // Even if we didn't find a UEI, if intel has an incumbent name, score as "other incumbent"
            if (string.IsNullOrEmpty(incumbentUei) && !string.IsNullOrEmpty(incumbentName))
            {
                return MakeFactor("Incumbent Advantage", 30, weight,
                    $"Incumbent: {incumbentName} (from Document Intel, no UEI match for vulnerability check)");
            }

            // Check if it's a recompete even without incumbent name
            if (string.IsNullOrEmpty(incumbentUei) && string.IsNullOrEmpty(incumbentName))
            {
                var isRecompete = await _context.OpportunityAttachmentSummaries.AsNoTracking()
                    .Where(s => s.NoticeId == opp.NoticeId
                           && s.IsRecompete != null
                           && s.IsRecompete.ToUpper() == "Y")
                    .AnyAsync();

                if (isRecompete)
                {
                    return MakeFactor("Incumbent Advantage", 50, weight,
                        "Re-compete identified by Document Intel but no incumbent name found");
                }
            }
        }

        decimal score;
        string detail;
        bool hadRealData = true;

        if (string.IsNullOrEmpty(incumbentUei))
        {
            // No incumbent identified — likely new requirement
            score = 70;
            detail = "No incumbent identified — likely a new requirement";
            hadRealData = false;
        }
        else if (linkedUeis.Count > 0 &&
                 linkedUeis.Any(u => string.Equals(incumbentUei, u, StringComparison.OrdinalIgnoreCase)))
        {
            score = 100;
            detail = "Your organization or a linked partner is the incumbent";
        }
        else
        {
            // Incumbent is someone else — check for vulnerability signals
            var vulnerabilities = await DetectIncumbentVulnerabilitiesAsync(incumbentUei, opp);
            var name = incumbentName ?? incumbentUei;

            if (vulnerabilities.Count > 0)
            {
                // Incumbent has vulnerability signals — better chance for us
                // Base score 30 + 10 per vulnerability, capped at 65
                score = (decimal)Math.Min(65.0, 30.0 + 10.0 * vulnerabilities.Count);
                detail = $"Incumbent: {name} — vulnerability signals: {string.Join(", ", vulnerabilities)}";
                suggestions.Add($"Incumbent {name} shows vulnerability ({string.Join("; ", vulnerabilities)}). Competitive opportunity.");
            }
            else
            {
                // Stable incumbent with no vulnerability signals
                score = 20;
                detail = $"Incumbent: {name} — no vulnerability signals detected";
                suggestions.Add($"Incumbent {name} appears stable. Strong differentiation strategy recommended.");
            }
        }

        return MakeFactor("Incumbent Advantage", score, weight, detail, hadRealData);
    }

    /// <summary>
    /// Detects vulnerability signals for an incumbent: expiring SAM registration,
    /// active exclusions, or over-spending on the contract.
    /// </summary>
    private async Task<List<string>> DetectIncumbentVulnerabilitiesAsync(string incumbentUei, Core.Models.Opportunity opp)
    {
        var signals = new List<string>();

        // Check SAM registration expiration (expiring within 6 months)
        var entity = await _context.Entities.AsNoTracking()
            .FirstOrDefaultAsync(e => e.UeiSam == incumbentUei);

        if (entity != null)
        {
            if (entity.RegistrationExpirationDate.HasValue)
            {
                var daysUntilExpiry = (entity.RegistrationExpirationDate.Value.ToDateTime(TimeOnly.MinValue) - DateTime.UtcNow).Days;
                if (daysUntilExpiry <= 180)
                    signals.Add(daysUntilExpiry <= 0
                        ? "SAM registration expired"
                        : $"SAM registration expiring in {daysUntilExpiry} days");
            }

            if (string.Equals(entity.ExclusionStatusFlag, "Y", StringComparison.OrdinalIgnoreCase))
            {
                signals.Add("entity has exclusion flag");
            }
        }

        // Check for active exclusions
        var hasExclusion = await _context.SamExclusions.AsNoTracking()
            .AnyAsync(e => e.Uei == incumbentUei
                && (e.TerminationDate == null || e.TerminationDate >= DateOnly.FromDateTime(DateTime.UtcNow)));
        if (hasExclusion)
            signals.Add("active exclusion record");

        // Check for over-spending: if contract obligations exceed base+all by >20%
        if (!string.IsNullOrEmpty(opp.SolicitationNumber))
        {
            var contractData = await _context.FpdsContracts.AsNoTracking()
                .Where(c => c.SolicitationNumber == opp.SolicitationNumber && c.VendorUei == incumbentUei)
                .Select(c => new { c.DollarsObligated, c.BaseAndAllOptions })
                .ToListAsync();

            if (contractData.Count > 0)
            {
                var totalObligated = contractData.Sum(c => c.DollarsObligated ?? 0);
                var totalBase = contractData.Sum(c => c.BaseAndAllOptions ?? 0);
                if (totalBase > 0 && totalObligated > totalBase * 1.2m)
                {
                    signals.Add($"over-spending ({totalObligated / totalBase:P0} of ceiling)");
                }
            }
        }

        return signals;
    }

    // -----------------------------------------------------------------------
    // Factor 5: Teaming Strength (weight 0.10)
    // -----------------------------------------------------------------------

    private async Task<PWinFactorDto> ScoreTeamingStrengthAsync(List<string> linkedUeis, string? naicsCode)
    {
        const decimal weight = 0.10m;

        if (linkedUeis.Count == 0)
        {
            return MakeFactor("Teaming Strength", 30, weight, "No UEI on file — teaming data unavailable", hadRealData: false);
        }

        // Find teaming partners from subaward data (any linked entity as prime or sub)
        var partnerUeisQuery = _context.SamSubawards.AsNoTracking()
            .Where(s => (s.PrimeUei != null && linkedUeis.Contains(s.PrimeUei))
                     || (s.SubUei != null && linkedUeis.Contains(s.SubUei)));

        // If NAICS is available, filter to relevant partners
        if (!string.IsNullOrEmpty(naicsCode))
        {
            partnerUeisQuery = partnerUeisQuery.Where(s => s.NaicsCode == naicsCode);
        }

        var partnerCount = await partnerUeisQuery
            .Select(s => linkedUeis.Contains(s.PrimeUei!) ? s.SubUei : s.PrimeUei)
            .Where(u => u != null && !linkedUeis.Contains(u))
            .Distinct()
            .CountAsync();

        decimal score;
        string detail;

        if (partnerCount >= 3)
        {
            score = 100;
            detail = $"Strong teaming network: {partnerCount} partner(s) with relevant experience";
        }
        else if (partnerCount >= 1)
        {
            score = 60;
            detail = $"Some teaming relationships: {partnerCount} partner(s) found";
        }
        else
        {
            score = 30;
            detail = "No teaming relationships found in subaward data";
        }

        return MakeFactor("Teaming Strength", score, weight, detail, hadRealData: partnerCount > 0);
    }

    // -----------------------------------------------------------------------
    // Factor 6: Time to Respond (weight 0.10)
    // Uses smooth continuous curve instead of hard buckets.
    // -----------------------------------------------------------------------

    /// <summary>
    /// Scores time to respond using a smooth curve: score = min(100, (daysRemaining / 45) * 100),
    /// clamped to [0, 100].
    /// </summary>
    private static PWinFactorDto ScoreTimeToRespond(DateTime? responseDeadline, List<string> suggestions)
    {
        const decimal weight = 0.10m;

        if (!responseDeadline.HasValue)
        {
            return MakeFactor("Time to Respond", 50, weight, "No response deadline set", hadRealData: false);
        }

        var daysLeft = (responseDeadline.Value - DateTime.UtcNow).TotalDays;

        decimal score;
        string detail;

        if (daysLeft < 0)
        {
            score = 0;
            detail = $"Deadline passed {Math.Abs((int)daysLeft)} day(s) ago";
        }
        else
        {
            // Smooth curve: scales linearly to 100 at 45 days, capped at 100
            var rawScore = Math.Min(100.0, (daysLeft / 45.0) * 100.0);
            score = (decimal)Math.Clamp(rawScore, 0.0, 100.0);
            score = Math.Round(score, 1);

            var daysInt = (int)daysLeft;
            if (daysInt < 7)
            {
                detail = $"Only {daysInt} day(s) until deadline";
                suggestions.Add($"Only {daysInt} day(s) until deadline. Expedite bid/no-bid decision.");
            }
            else if (daysInt <= 45)
            {
                detail = $"{daysInt} days until deadline";
            }
            else
            {
                detail = $"{daysInt} days until deadline — ample time to prepare";
            }
        }

        return MakeFactor("Time to Respond", score, weight, detail);
    }

    // -----------------------------------------------------------------------
    // Factor 7: Contract Value Fit (weight 0.10)
    // Uses smooth exponential falloff instead of hard thresholds.
    // -----------------------------------------------------------------------

    /// <summary>
    /// Scores contract value fit using smooth exponential decay based on the ratio
    /// between opportunity value and historical average: score = 100 * exp(-0.5 * max(0, fitRatio - 1)),
    /// clamped to [10, 100].
    /// </summary>
    private async Task<PWinFactorDto> ScoreContractValueFitAsync(decimal? estimatedValue, int orgId, List<string> linkedUeis)
    {
        const decimal weight = 0.10m;

        if (!estimatedValue.HasValue || estimatedValue.Value <= 0)
        {
            return MakeFactor("Contract Value Fit", 50, weight, "No estimated value on opportunity", hadRealData: false);
        }

        // Get average contract size from past performance + FPDS
        var ppValues = await _context.OrganizationPastPerformances.AsNoTracking()
            .Where(p => p.OrganizationId == orgId && p.ContractValue != null && p.ContractValue > 0)
            .Select(p => p.ContractValue!.Value)
            .ToListAsync();

        if (linkedUeis.Count > 0)
        {
            var fpdsValues = await _context.FpdsContracts.AsNoTracking()
                .Where(c => c.VendorUei != null && linkedUeis.Contains(c.VendorUei) && c.BaseAndAllOptions != null && c.BaseAndAllOptions > 0)
                .Select(c => c.BaseAndAllOptions!.Value)
                .Take(100) // Limit to avoid pulling too many rows
                .ToListAsync();

            ppValues.AddRange(fpdsValues);
        }

        if (ppValues.Count == 0)
        {
            return MakeFactor("Contract Value Fit", 50, weight,
                $"No historical contract values to compare against ${estimatedValue.Value:N0}", hadRealData: false);
        }

        var avgValue = ppValues.Average();
        var ratio = (double)(estimatedValue.Value / avgValue);
        // Use the larger/smaller ratio so direction doesn't matter
        var fitRatio = ratio > 1 ? ratio : 1.0 / ratio;

        // Smooth exponential decay: perfect fit (ratio=1) = 100, decays as ratio grows
        var rawScore = 100.0 * Math.Exp(-0.5 * Math.Max(0, fitRatio - 1));
        var score = (decimal)Math.Clamp(rawScore, 10.0, 100.0);
        score = Math.Round(score, 1);

        var detail = $"Opportunity ${estimatedValue.Value:N0} vs. avg contract ${avgValue:N0} ({fitRatio:F1}x ratio, score {score:F0})";

        return MakeFactor("Contract Value Fit", score, weight, detail);
    }

    // -----------------------------------------------------------------------
    // Helpers
    // -----------------------------------------------------------------------

    /// <summary>
    /// Creates a PWinFactorDto with computed weighted score and data completeness tracking.
    /// </summary>
    private static PWinFactorDto MakeFactor(string name, decimal score, decimal weight, string detail, bool hadRealData = true)
    {
        return new PWinFactorDto
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
