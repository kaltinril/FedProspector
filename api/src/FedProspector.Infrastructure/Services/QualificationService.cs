using FedProspector.Core.DTOs.Intelligence;
using FedProspector.Core.Interfaces;
using FedProspector.Infrastructure.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;

namespace FedProspector.Infrastructure.Services;

public class QualificationService : IQualificationService
{
    private readonly FedProspectorDbContext _context;
    private readonly ILogger<QualificationService> _logger;

    /// <summary>
    /// Maps set-aside codes to the certification types they require.
    /// </summary>
    private static readonly Dictionary<string, string> SetAsideCertMap = new(StringComparer.OrdinalIgnoreCase)
    {
        ["WOSB"] = "WOSB",
        ["WOSBSS"] = "WOSB",
        ["EDWOSB"] = "EDWOSB",
        ["EDWOSBSS"] = "EDWOSB",
        ["8A"] = "8(a)",
        ["8AN"] = "8(a)",
        ["HZC"] = "HUBZone",
        ["HZS"] = "HUBZone",
        ["SDVOSBC"] = "SDVOSB",
        ["SDVOSBS"] = "SDVOSB",
        ["SBA"] = "SDB",
        ["SBP"] = "SDB",
    };

    private static readonly string[] SecurityKeywords =
    [
        "top secret", "ts/sci", "secret clearance", "security clearance",
        "public trust", "clearance required", "classified"
    ];

    public QualificationService(FedProspectorDbContext context, ILogger<QualificationService> logger)
    {
        _context = context;
        _logger = logger;
    }

    public async Task<QualificationCheckDto> CheckQualificationAsync(string noticeId, int orgId)
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

        var checks = new List<QualificationItemDto>();

        // --- Certification checks ---
        checks.Add(CheckSetAsideMatch(opp.SetAsideCode, orgCerts));
        checks.Add(await CheckNaicsMatchAsync(opp.NaicsCode, orgId));
        checks.Add(await CheckSamRegistrationAsync(org.UeiSam));

        // --- Experience checks ---
        checks.Add(await CheckPastPerformanceAsync(opp.NaicsCode, orgId, org.UeiSam));

        // --- Compliance checks ---
        checks.Add(await CheckSizeStandardAsync(opp.NaicsCode, orgId));
        checks.Add(CheckSecurityClearance(opp.Title, opp.DescriptionText));

        // --- Logistics checks ---
        checks.Add(CheckPlaceOfPerformance(opp.PopCountry));
        checks.Add(CheckResponseDeadline(opp.ResponseDeadline));

        var passCount = checks.Count(c => c.Status == "Pass");
        var failCount = checks.Count(c => c.Status == "Fail");
        var warningCount = checks.Count(c => c.Status == "Warning");

        var overallStatus = failCount switch
        {
            0 => "Qualified",
            1 or 2 => "Partially Qualified",
            _ => "Not Qualified"
        };

        _logger.LogInformation(
            "Qualification check for opportunity {NoticeId}, org {OrgId}: {Status} ({Pass}P/{Fail}F/{Warning}W)",
            noticeId, orgId, overallStatus, passCount, failCount, warningCount);

        return new QualificationCheckDto
        {
            NoticeId = noticeId,
            PassCount = passCount,
            FailCount = failCount,
            WarningCount = warningCount,
            TotalChecks = checks.Count,
            OverallStatus = overallStatus,
            Checks = checks
        };
    }

    private static QualificationItemDto CheckSetAsideMatch(string? setAsideCode, List<string> orgCerts)
    {
        var code = (setAsideCode ?? "").Trim();

        if (string.IsNullOrEmpty(code))
        {
            return new QualificationItemDto
            {
                Name = "Set-Aside Match",
                Category = "Certification",
                Status = "Pass",
                Detail = "Unrestricted"
            };
        }

        if (SetAsideCertMap.TryGetValue(code, out var requiredCert))
        {
            var hasCert = orgCerts.Any(c => string.Equals(c, requiredCert, StringComparison.OrdinalIgnoreCase));
            return new QualificationItemDto
            {
                Name = "Set-Aside Match",
                Category = "Certification",
                Status = hasCert ? "Pass" : "Fail",
                Detail = hasCert
                    ? $"Organization holds {requiredCert} certification for {code} set-aside"
                    : $"Organization lacks required {requiredCert} certification for {code} set-aside"
            };
        }

        return new QualificationItemDto
        {
            Name = "Set-Aside Match",
            Category = "Certification",
            Status = "Warning",
            Detail = $"Unknown set-aside type: {code}"
        };
    }

    private async Task<QualificationItemDto> CheckNaicsMatchAsync(string? naicsCode, int orgId)
    {
        if (string.IsNullOrEmpty(naicsCode))
        {
            return new QualificationItemDto
            {
                Name = "NAICS Code Match",
                Category = "Certification",
                Status = "Warning",
                Detail = "No NAICS code on opportunity"
            };
        }

        var hasNaics = await _context.OrganizationNaics.AsNoTracking()
            .AnyAsync(n => n.OrganizationId == orgId && n.NaicsCode == naicsCode);

        return new QualificationItemDto
        {
            Name = "NAICS Code Match",
            Category = "Certification",
            Status = hasNaics ? "Pass" : "Fail",
            Detail = hasNaics
                ? $"Organization registered for NAICS {naicsCode}"
                : $"Organization not registered for NAICS {naicsCode}"
        };
    }

    private async Task<QualificationItemDto> CheckSamRegistrationAsync(string? ueiSam)
    {
        if (string.IsNullOrEmpty(ueiSam))
        {
            return new QualificationItemDto
            {
                Name = "SAM.gov Registration",
                Category = "Certification",
                Status = "Fail",
                Detail = "No UEI on file for organization"
            };
        }

        var entity = await _context.Entities.AsNoTracking()
            .Where(e => e.UeiSam == ueiSam)
            .Select(e => new { e.RegistrationStatus, e.RegistrationExpirationDate })
            .FirstOrDefaultAsync();

        if (entity == null)
        {
            return new QualificationItemDto
            {
                Name = "SAM.gov Registration",
                Category = "Certification",
                Status = "Fail",
                Detail = $"UEI {ueiSam} not found in SAM.gov entity data"
            };
        }

        if (entity.RegistrationStatus != "A")
        {
            return new QualificationItemDto
            {
                Name = "SAM.gov Registration",
                Category = "Certification",
                Status = "Fail",
                Detail = "SAM.gov registration is not active"
            };
        }

        // Check if expiring within 90 days
        if (entity.RegistrationExpirationDate.HasValue)
        {
            var daysUntilExpiration = (entity.RegistrationExpirationDate.Value.ToDateTime(TimeOnly.MinValue) - DateTime.UtcNow).Days;
            if (daysUntilExpiration <= 90)
            {
                return new QualificationItemDto
                {
                    Name = "SAM.gov Registration",
                    Category = "Certification",
                    Status = "Warning",
                    Detail = $"SAM.gov registration expiring in {daysUntilExpiration} day(s)"
                };
            }
        }

        return new QualificationItemDto
        {
            Name = "SAM.gov Registration",
            Category = "Certification",
            Status = "Pass",
            Detail = "SAM.gov registration is active"
        };
    }

    private async Task<QualificationItemDto> CheckPastPerformanceAsync(string? naicsCode, int orgId, string? orgUei)
    {
        if (string.IsNullOrEmpty(naicsCode))
        {
            return new QualificationItemDto
            {
                Name = "Past Performance",
                Category = "Experience",
                Status = "Warning",
                Detail = "No NAICS code on opportunity to match against"
            };
        }

        var ppCount = await _context.OrganizationPastPerformances.AsNoTracking()
            .Where(p => p.OrganizationId == orgId && p.NaicsCode == naicsCode)
            .CountAsync();

        var fpdsCount = 0;
        if (!string.IsNullOrEmpty(orgUei))
        {
            fpdsCount = await _context.FpdsContracts.AsNoTracking()
                .Where(c => c.VendorUei == orgUei && c.NaicsCode == naicsCode)
                .Select(c => c.ContractId)
                .Distinct()
                .CountAsync();
        }

        var total = ppCount + fpdsCount;

        string status;
        string detail;
        if (total >= 3)
        {
            status = "Pass";
            detail = $"{total} past performance record(s) in NAICS {naicsCode}";
        }
        else if (total >= 1)
        {
            status = "Warning";
            detail = $"Only {total} past performance record(s) in NAICS {naicsCode}";
        }
        else
        {
            status = "Fail";
            detail = $"No past performance found in NAICS {naicsCode}";
        }

        return new QualificationItemDto
        {
            Name = "Past Performance",
            Category = "Experience",
            Status = status,
            Detail = detail
        };
    }

    private async Task<QualificationItemDto> CheckSizeStandardAsync(string? naicsCode, int orgId)
    {
        if (string.IsNullOrEmpty(naicsCode))
        {
            return new QualificationItemDto
            {
                Name = "Size Standard",
                Category = "Compliance",
                Status = "Warning",
                Detail = "No NAICS code on opportunity"
            };
        }

        var orgNaics = await _context.OrganizationNaics.AsNoTracking()
            .FirstOrDefaultAsync(n => n.OrganizationId == orgId && n.NaicsCode == naicsCode);

        if (orgNaics == null)
        {
            return new QualificationItemDto
            {
                Name = "Size Standard",
                Category = "Compliance",
                Status = "Warning",
                Detail = $"NAICS {naicsCode} not tracked in organization profile"
            };
        }

        return new QualificationItemDto
        {
            Name = "Size Standard",
            Category = "Compliance",
            Status = orgNaics.SizeStandardMet == "Y" ? "Pass" : "Fail",
            Detail = orgNaics.SizeStandardMet == "Y"
                ? $"Size standard met for NAICS {naicsCode}"
                : $"Size standard not met for NAICS {naicsCode}"
        };
    }

    private static QualificationItemDto CheckSecurityClearance(string? title, string? description)
    {
        var text = $"{title} {description}".ToLowerInvariant();

        foreach (var keyword in SecurityKeywords)
        {
            if (text.Contains(keyword, StringComparison.OrdinalIgnoreCase))
            {
                return new QualificationItemDto
                {
                    Name = "Security Clearance",
                    Category = "Compliance",
                    Status = "Warning",
                    Detail = $"Security clearance may be required: \"{keyword}\""
                };
            }
        }

        return new QualificationItemDto
        {
            Name = "Security Clearance",
            Category = "Compliance",
            Status = "Pass",
            Detail = "No security clearance keywords detected"
        };
    }

    private static QualificationItemDto CheckPlaceOfPerformance(string? popCountry)
    {
        if (!string.IsNullOrEmpty(popCountry) &&
            !string.Equals(popCountry, "USA", StringComparison.OrdinalIgnoreCase) &&
            !string.Equals(popCountry, "US", StringComparison.OrdinalIgnoreCase))
        {
            return new QualificationItemDto
            {
                Name = "Place of Performance",
                Category = "Logistics",
                Status = "Warning",
                Detail = $"OCONUS performance location: {popCountry}"
            };
        }

        return new QualificationItemDto
        {
            Name = "Place of Performance",
            Category = "Logistics",
            Status = "Pass",
            Detail = "Domestic performance location"
        };
    }

    private static QualificationItemDto CheckResponseDeadline(DateTime? responseDeadline)
    {
        if (!responseDeadline.HasValue)
        {
            return new QualificationItemDto
            {
                Name = "Response Deadline",
                Category = "Logistics",
                Status = "Pass",
                Detail = "No response deadline set"
            };
        }

        var daysLeft = (responseDeadline.Value - DateTime.UtcNow).Days;

        if (daysLeft < 0)
        {
            return new QualificationItemDto
            {
                Name = "Response Deadline",
                Category = "Logistics",
                Status = "Fail",
                Detail = "Deadline has passed"
            };
        }

        if (daysLeft < 7)
        {
            return new QualificationItemDto
            {
                Name = "Response Deadline",
                Category = "Logistics",
                Status = "Warning",
                Detail = $"Only {daysLeft} days remaining"
            };
        }

        return new QualificationItemDto
        {
            Name = "Response Deadline",
            Category = "Logistics",
            Status = "Pass",
            Detail = $"{daysLeft} days until deadline"
        };
    }
}
