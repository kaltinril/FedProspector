using FedProspector.Core.DTOs.Intelligence;
using FedProspector.Core.Interfaces;
using FedProspector.Infrastructure.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;

namespace FedProspector.Infrastructure.Services;

public class PWinService : IPWinService
{
    private readonly FedProspectorDbContext _context;
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

    public PWinService(FedProspectorDbContext context, ILogger<PWinService> logger)
    {
        _context = context;
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

        var orgNaics = await _context.OrganizationNaics.AsNoTracking()
            .Where(n => n.OrganizationId == orgId)
            .Select(n => n.NaicsCode)
            .ToListAsync();

        var factors = new List<PWinFactorDto>();
        var suggestions = new List<string>();

        // 1. Set-aside match (weight 0.20)
        var setAsideFactor = ScoreSetAsideMatch(opp.SetAsideCode, orgCerts, suggestions);
        factors.Add(setAsideFactor);

        // 2. NAICS experience (weight 0.20)
        var naicsFactor = await ScoreNaicsExperienceAsync(opp.NaicsCode, orgId, org.UeiSam, suggestions);
        factors.Add(naicsFactor);

        // 3. Competition level (weight 0.15)
        var competitionFactor = await ScoreCompetitionLevelAsync(opp.NaicsCode);
        factors.Add(competitionFactor);

        // 4. Incumbent advantage (weight 0.15)
        var incumbentFactor = await ScoreIncumbentAdvantageAsync(opp, org.UeiSam, suggestions);
        factors.Add(incumbentFactor);

        // 5. Teaming strength (weight 0.10)
        var teamingFactor = await ScoreTeamingStrengthAsync(org.UeiSam, opp.NaicsCode);
        factors.Add(teamingFactor);

        // 6. Time to respond (weight 0.10)
        var timeFactor = ScoreTimeToRespond(opp.ResponseDeadline, suggestions);
        factors.Add(timeFactor);

        // 7. Contract value fit (weight 0.10)
        var valueFactor = await ScoreContractValueFitAsync(opp.EstimatedContractValue, orgId, org.UeiSam);
        factors.Add(valueFactor);

        var totalScore = factors.Sum(f => f.WeightedScore);
        totalScore = Math.Round(totalScore, 1);

        var category = totalScore switch
        {
            >= 70 => "High",
            >= 40 => "Medium",
            >= 15 => "Low",
            _ => "VeryLow"
        };

        // Look up prospect if one exists
        var prospectId = await _context.Prospects.AsNoTracking()
            .Where(p => p.NoticeId == noticeId && p.OrganizationId == orgId)
            .Select(p => (int?)p.ProspectId)
            .FirstOrDefaultAsync();

        _logger.LogInformation("pWin calculated for opportunity {NoticeId}, org {OrgId}: {Score}% ({Category})",
            noticeId, orgId, totalScore, category);

        return new PWinResultDto
        {
            ProspectId = prospectId,
            NoticeId = noticeId,
            Score = totalScore,
            Category = category,
            Factors = factors,
            Suggestions = suggestions
        };
    }

    private static PWinFactorDto ScoreSetAsideMatch(string? setAsideCode, List<string> orgCerts, List<string> suggestions)
    {
        const decimal weight = 0.20m;
        var code = (setAsideCode ?? "").Trim();

        decimal score;
        string detail;

        if (string.IsNullOrEmpty(code))
        {
            score = 50;
            detail = "Full and open competition (no set-aside)";
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
        }

        return new PWinFactorDto
        {
            Name = "Set-Aside Match",
            Score = score,
            Weight = weight,
            WeightedScore = Math.Round(score * weight, 2),
            Detail = detail
        };
    }

    private async Task<PWinFactorDto> ScoreNaicsExperienceAsync(string? naicsCode, int orgId, string? orgUei, List<string> suggestions)
    {
        const decimal weight = 0.20m;

        if (string.IsNullOrEmpty(naicsCode))
        {
            return MakeFactor("NAICS Experience", 50, weight, "No NAICS code on opportunity");
        }

        // Count past performance records for this NAICS
        var ppCount = await _context.OrganizationPastPerformances.AsNoTracking()
            .Where(p => p.OrganizationId == orgId && p.NaicsCode == naicsCode)
            .CountAsync();

        // Count FPDS contracts where org is vendor
        var fpdsCount = 0;
        if (!string.IsNullOrEmpty(orgUei))
        {
            fpdsCount = await _context.FpdsContracts.AsNoTracking()
                .Where(c => c.VendorUei == orgUei && c.NaicsCode == naicsCode)
                .Select(c => c.ContractId)
                .Distinct()
                .CountAsync();
        }

        var totalExperience = ppCount + fpdsCount;
        decimal score;
        string detail;

        if (totalExperience >= 5)
        {
            score = 100;
            detail = $"Strong experience in NAICS {naicsCode} ({totalExperience} contracts/records)";
        }
        else if (totalExperience >= 3)
        {
            score = 75;
            detail = $"Good experience in NAICS {naicsCode} ({totalExperience} contracts/records)";
        }
        else if (totalExperience >= 1)
        {
            score = 50;
            detail = $"Limited experience in NAICS {naicsCode} ({totalExperience} contracts/records)";
        }
        else
        {
            score = 10;
            detail = $"No past performance found in NAICS {naicsCode}";
            suggestions.Add($"Limited past performance in NAICS {naicsCode}. Consider teaming with experienced partners.");
        }

        return MakeFactor("NAICS Experience", score, weight, detail);
    }

    private async Task<PWinFactorDto> ScoreCompetitionLevelAsync(string? naicsCode)
    {
        const decimal weight = 0.15m;

        if (string.IsNullOrEmpty(naicsCode))
        {
            return MakeFactor("Competition Level", 50, weight, "No NAICS code — competition level unknown");
        }

        var threeYearsAgo = DateOnly.FromDateTime(DateTime.UtcNow.AddYears(-3));
        var distinctVendors = await _context.FpdsContracts.AsNoTracking()
            .Where(c => c.NaicsCode == naicsCode
                        && c.DateSigned != null
                        && c.DateSigned >= threeYearsAgo
                        && c.VendorUei != null)
            .Select(c => c.VendorUei)
            .Distinct()
            .CountAsync();

        decimal score;
        string detail;

        if (distinctVendors == 0)
        {
            score = 50;
            detail = $"No FPDS contract data found for NAICS {naicsCode} in last 3 years";
        }
        else if (distinctVendors <= 3)
        {
            score = 100;
            detail = $"Low competition: {distinctVendors} vendor(s) in NAICS {naicsCode} (last 3 years)";
        }
        else if (distinctVendors <= 6)
        {
            score = 70;
            detail = $"Moderate competition: {distinctVendors} vendors in NAICS {naicsCode} (last 3 years)";
        }
        else if (distinctVendors <= 10)
        {
            score = 40;
            detail = $"High competition: {distinctVendors} vendors in NAICS {naicsCode} (last 3 years)";
        }
        else
        {
            score = 20;
            detail = $"Very high competition: {distinctVendors} vendors in NAICS {naicsCode} (last 3 years)";
        }

        return MakeFactor("Competition Level", score, weight, detail);
    }

    private async Task<PWinFactorDto> ScoreIncumbentAdvantageAsync(
        Core.Models.Opportunity opp, string? orgUei, List<string> suggestions)
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

        decimal score;
        string detail;

        if (string.IsNullOrEmpty(incumbentUei))
        {
            // No incumbent identified — likely new requirement
            score = 70;
            detail = "No incumbent identified — likely a new requirement";
        }
        else if (!string.IsNullOrEmpty(orgUei) &&
                 string.Equals(incumbentUei, orgUei, StringComparison.OrdinalIgnoreCase))
        {
            score = 100;
            detail = "Your organization is the incumbent";
        }
        else
        {
            score = 30;
            var name = incumbentName ?? incumbentUei;
            detail = $"Incumbent: {name}";
            suggestions.Add($"Incumbent {name} has won this contract previously. Differentiation strategy recommended.");
        }

        return MakeFactor("Incumbent Advantage", score, weight, detail);
    }

    private async Task<PWinFactorDto> ScoreTeamingStrengthAsync(string? orgUei, string? naicsCode)
    {
        const decimal weight = 0.10m;

        if (string.IsNullOrEmpty(orgUei))
        {
            return MakeFactor("Teaming Strength", 30, weight, "No UEI on file — teaming data unavailable");
        }

        // Find teaming partners from subaward data (org as prime or sub)
        var partnerUeisQuery = _context.SamSubawards.AsNoTracking()
            .Where(s => s.PrimeUei == orgUei || s.SubUei == orgUei);

        // If NAICS is available, filter to relevant partners
        if (!string.IsNullOrEmpty(naicsCode))
        {
            partnerUeisQuery = partnerUeisQuery.Where(s => s.NaicsCode == naicsCode);
        }

        var partnerCount = await partnerUeisQuery
            .Select(s => s.PrimeUei == orgUei ? s.SubUei : s.PrimeUei)
            .Where(u => u != null)
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

        return MakeFactor("Teaming Strength", score, weight, detail);
    }

    private static PWinFactorDto ScoreTimeToRespond(DateTime? responseDeadline, List<string> suggestions)
    {
        const decimal weight = 0.10m;

        if (!responseDeadline.HasValue)
        {
            return MakeFactor("Time to Respond", 50, weight, "No response deadline set");
        }

        var daysLeft = (responseDeadline.Value - DateTime.UtcNow).Days;

        decimal score;
        string detail;

        if (daysLeft < 0)
        {
            score = 0;
            detail = $"Deadline passed {Math.Abs(daysLeft)} day(s) ago";
        }
        else if (daysLeft < 7)
        {
            score = 10;
            detail = $"Only {daysLeft} day(s) until deadline";
            suggestions.Add($"Only {daysLeft} day(s) until deadline. Expedite bid/no-bid decision.");
        }
        else if (daysLeft < 14)
        {
            score = 40;
            detail = $"{daysLeft} days until deadline";
        }
        else if (daysLeft <= 30)
        {
            score = 70;
            detail = $"{daysLeft} days until deadline";
        }
        else
        {
            score = 100;
            detail = $"{daysLeft} days until deadline — ample time to prepare";
        }

        return MakeFactor("Time to Respond", score, weight, detail);
    }

    private async Task<PWinFactorDto> ScoreContractValueFitAsync(decimal? estimatedValue, int orgId, string? orgUei)
    {
        const decimal weight = 0.10m;

        if (!estimatedValue.HasValue || estimatedValue.Value <= 0)
        {
            return MakeFactor("Contract Value Fit", 50, weight, "No estimated value on opportunity");
        }

        // Get average contract size from past performance + FPDS
        var ppValues = await _context.OrganizationPastPerformances.AsNoTracking()
            .Where(p => p.OrganizationId == orgId && p.ContractValue != null && p.ContractValue > 0)
            .Select(p => p.ContractValue!.Value)
            .ToListAsync();

        if (!string.IsNullOrEmpty(orgUei))
        {
            var fpdsValues = await _context.FpdsContracts.AsNoTracking()
                .Where(c => c.VendorUei == orgUei && c.BaseAndAllOptions != null && c.BaseAndAllOptions > 0)
                .Select(c => c.BaseAndAllOptions!.Value)
                .Take(100) // Limit to avoid pulling too many rows
                .ToListAsync();

            ppValues.AddRange(fpdsValues);
        }

        if (ppValues.Count == 0)
        {
            return MakeFactor("Contract Value Fit", 50, weight,
                $"No historical contract values to compare against ${estimatedValue.Value:N0}");
        }

        var avgValue = ppValues.Average();
        var ratio = (double)(estimatedValue.Value / avgValue);
        // Use the larger/smaller ratio so direction doesn't matter
        var fitRatio = ratio > 1 ? ratio : 1.0 / ratio;

        decimal score;
        string detail;

        if (fitRatio <= 2.0)
        {
            score = 100;
            detail = $"Good fit: opportunity ${estimatedValue.Value:N0} vs. avg contract ${avgValue:N0}";
        }
        else if (fitRatio <= 5.0)
        {
            score = 60;
            detail = $"Moderate fit: opportunity ${estimatedValue.Value:N0} vs. avg contract ${avgValue:N0} ({fitRatio:F1}x difference)";
        }
        else
        {
            score = 30;
            detail = $"Poor fit: opportunity ${estimatedValue.Value:N0} vs. avg contract ${avgValue:N0} ({fitRatio:F1}x difference)";
        }

        return MakeFactor("Contract Value Fit", score, weight, detail);
    }

    private static PWinFactorDto MakeFactor(string name, decimal score, decimal weight, string detail)
    {
        return new PWinFactorDto
        {
            Name = name,
            Score = score,
            Weight = weight,
            WeightedScore = Math.Round(score * weight, 2),
            Detail = detail
        };
    }
}
