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
    /// All set-aside codes considered "small business" for partial-match scoring.
    /// </summary>
    private static readonly HashSet<string> SmallBusinessSetAsides = new(StringComparer.OrdinalIgnoreCase)
    {
        "WOSB", "WOSBSS", "EDWOSB", "EDWOSBSS", "8A", "8AN",
        "SBA", "SBP", "HZC", "HZS", "SDVOSBC", "SDVOSBS"
    };

    public RecommendedOpportunityService(
        FedProspectorDbContext context,
        ILogger<RecommendedOpportunityService> logger)
    {
        _context = context;
        _logger = logger;
    }

    public async Task<List<RecommendedOpportunityDto>> GetRecommendedAsync(int orgId, int limit = 10)
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

        // 2. Query active opportunities matching org NAICS codes
        var now = DateTime.UtcNow;
        var candidates = await _context.Opportunities.AsNoTracking()
            .Where(o => naicsCodes.Contains(o.NaicsCode!)
                        && o.Active != "N"
                        && !OpportunityFilters.NonBiddableTypes.Contains(o.Type!)
                        && (o.ResponseDeadline == null || o.ResponseDeadline > now))
            .Select(o => new
            {
                o.NoticeId,
                o.Title,
                o.SolicitationNumber,
                o.DepartmentName,
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
                o.PopCountry
            })
            .ToListAsync();

        // 3. Dedup: keep latest notice per solicitation
        var deduped = candidates
            .GroupBy(c => string.IsNullOrEmpty(c.SolicitationNumber) ? c.NoticeId : c.SolicitationNumber)
            .Select(g => g.OrderByDescending(c => c.PostedDate).ThenByDescending(c => c.NoticeId).First())
            .ToList();

        // 4. Filter by set-aside compatibility and score
        var scored = new List<(RecommendedOpportunityDto Dto, decimal RawScore)>();

        foreach (var c in deduped)
        {
            var setAsideCode = (c.SetAsideCode ?? "").Trim();

            // Set-aside filtering: skip if there's a set-aside that requires a cert we don't have
            // and it's not a general small business set-aside we might partially qualify for
            // (We still include them but score them lower)

            // Score calculation (out of 60)
            decimal score = 0;
            decimal setAsidePoints = 0;
            decimal naicsPoints = 0;
            decimal timePoints = 0;
            decimal valuePoints = 0;

            // Set-aside match: exact cert match = 20pts, any small business set-aside = 10pts, none = 0pts
            if (string.IsNullOrEmpty(setAsideCode))
            {
                // Unrestricted — no bonus
            }
            else if (SetAsideToCertType.TryGetValue(setAsideCode, out var requiredCert)
                     && orgCertSet.Contains(requiredCert))
            {
                setAsidePoints = 20;
            }
            else if (SmallBusinessSetAsides.Contains(setAsideCode) && orgCertSet.Count > 0)
            {
                // Org has some cert, but not the exact match
                setAsidePoints = 10;
            }
            else if (!string.IsNullOrEmpty(setAsideCode) && SetAsideToCertType.ContainsKey(setAsideCode))
            {
                // Set-aside requires a cert we don't have — skip entirely
                continue;
            }
            score += setAsidePoints;

            // NAICS match: primary = 20pts, secondary = 15pts
            if (primaryNaics.Contains(c.NaicsCode!))
                naicsPoints = 20;
            else
                naicsPoints = 15;
            score += naicsPoints;

            // Time remaining
            if (c.ResponseDeadline.HasValue)
            {
                var daysLeft = (c.ResponseDeadline.Value - now).Days;
                timePoints = daysLeft switch
                {
                    >= 30 => 10,
                    >= 14 => 7,
                    >= 7 => 4,
                    _ => 1
                };
            }
            else
            {
                timePoints = 5;
            }
            score += timePoints;

            // Value scoring — use EstimatedContractValue if available, else AwardAmount
            var value = c.EstimatedContractValue ?? c.AwardAmount;
            if (value.HasValue)
            {
                valuePoints = value.Value switch
                {
                    > 1_000_000m => 10,
                    > 500_000m => 8,
                    > 100_000m => 6,
                    > 50_000m => 4,
                    _ => 2
                };
            }
            else
            {
                valuePoints = 3;
            }
            score += valuePoints;

            // Normalize to 0-100
            var normalized = Math.Round(score / 60m * 100m, 1);

            var category = normalized switch
            {
                >= 70 => "High",
                >= 40 => "Medium",
                >= 15 => "Low",
                _ => "VeryLow"
            };

            int? daysRemaining = c.ResponseDeadline.HasValue
                ? (int)(c.ResponseDeadline.Value - now).TotalDays
                : null;

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
                QScore = normalized,
                QScoreCategory = category,
                QScoreFactors = new List<QScoreFactorDto>
                {
                    new() { Name = "Set-Aside Match", Points = setAsidePoints, MaxPoints = 20 },
                    new() { Name = "NAICS Match", Points = naicsPoints, MaxPoints = 20 },
                    new() { Name = "Time Remaining", Points = timePoints, MaxPoints = 10 },
                    new() { Name = "Contract Value", Points = valuePoints, MaxPoints = 10 }
                }
            };

            scored.Add((dto, normalized));
        }

        // 5. Order by score DESC, take top N
        var topN = scored
            .OrderByDescending(s => s.RawScore)
            .Take(limit)
            .Select(s => s.Dto)
            .ToList();

        // 6. Enrich with NAICS descriptions (batch lookup)
        var distinctNaics = topN
            .Where(d => d.NaicsCode != null)
            .Select(d => d.NaicsCode!)
            .Distinct()
            .ToList();

        var naicsDescriptions = await _context.RefNaicsCodes.AsNoTracking()
            .Where(n => distinctNaics.Contains(n.NaicsCode))
            .ToDictionaryAsync(n => n.NaicsCode, n => n.Description);

        // 7. Check re-compete status (batch lookup by solicitation numbers)
        var solNums = topN
            .Where(d => !string.IsNullOrEmpty(d.SolicitationNumber))
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

        // 8. Apply enrichments
        foreach (var dto in topN)
        {
            if (dto.NaicsCode != null && naicsDescriptions.TryGetValue(dto.NaicsCode, out var desc))
                dto.NaicsDescription = desc;

            if (!string.IsNullOrEmpty(dto.SolicitationNumber)
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
}
