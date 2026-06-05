using FedProspector.Core.DTOs.Organizations;
using FedProspector.Core.Interfaces;
using FedProspector.Core.Models;
using FedProspector.Infrastructure.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;

namespace FedProspector.Infrastructure.Services;

public class CompanyProfileService : ICompanyProfileService
{
    private readonly FedProspectorDbContext _context;
    private readonly ILogger<CompanyProfileService> _logger;

    public CompanyProfileService(
        FedProspectorDbContext context,
        ILogger<CompanyProfileService> logger)
    {
        _context = context;
        _logger = logger;
    }

    public async Task<OrgProfileDto> GetProfileAsync(int orgId)
    {
        var org = await _context.Organizations
            .AsNoTracking()
            .Include(o => o.NaicsCodes)
            .Include(o => o.Certifications)
            .FirstOrDefaultAsync(o => o.OrganizationId == orgId)
            ?? throw new KeyNotFoundException($"Organization {orgId} not found.");

        return MapToProfileDto(org);
    }

    public async Task<OrgProfileDto> UpdateProfileAsync(int orgId, UpdateOrgProfileRequest request)
    {
        var org = await _context.Organizations
            .Include(o => o.NaicsCodes)
            .Include(o => o.Certifications)
            .FirstOrDefaultAsync(o => o.OrganizationId == orgId)
            ?? throw new KeyNotFoundException($"Organization {orgId} not found.");

        if (request.Name != null) org.Name = request.Name;
        if (request.LegalName != null) org.LegalName = request.LegalName;
        if (request.DbaName != null) org.DbaName = request.DbaName;
        if (request.UeiSam != null) org.UeiSam = request.UeiSam;
        if (request.CageCode != null) org.CageCode = request.CageCode;
        if (request.Ein != null) org.Ein = request.Ein;
        if (request.AddressLine1 != null) org.AddressLine1 = request.AddressLine1;
        if (request.AddressLine2 != null) org.AddressLine2 = request.AddressLine2;
        if (request.City != null) org.City = request.City;
        if (request.StateCode != null) org.StateCode = request.StateCode;
        if (request.ZipCode != null) org.ZipCode = request.ZipCode;
        if (request.CountryCode != null) org.CountryCode = request.CountryCode;
        if (request.Phone != null) org.Phone = request.Phone;
        if (request.Website != null) org.Website = request.Website;
        if (request.EmployeeCount.HasValue) org.EmployeeCount = request.EmployeeCount;
        if (request.AnnualRevenue.HasValue) org.AnnualRevenue = request.AnnualRevenue;
        if (request.FiscalYearEndMonth.HasValue) org.FiscalYearEndMonth = request.FiscalYearEndMonth;
        if (request.EntityStructure != null) org.EntityStructure = request.EntityStructure;

        if (request.ProfileCompleted.HasValue)
        {
            org.ProfileCompleted = request.ProfileCompleted.Value ? "Y" : "N";
            if (request.ProfileCompleted.Value && org.ProfileCompletedAt == null)
            {
                org.ProfileCompletedAt = DateTime.UtcNow;
            }
        }

        org.UpdatedAt = DateTime.UtcNow;
        await _context.SaveChangesAsync();

        _logger.LogInformation("Organization {OrgId} profile updated", orgId);

        return MapToProfileDto(org);
    }

    public async Task<List<OrgNaicsDto>> GetNaicsAsync(int orgId)
    {
        return await _context.OrganizationNaics
            .AsNoTracking()
            .Where(n => n.OrganizationId == orgId)
            .OrderByDescending(n => n.IsPrimary)
            .ThenBy(n => n.NaicsCode)
            .Select(n => new OrgNaicsDto
            {
                Id = n.Id,
                NaicsCode = n.NaicsCode,
                IsPrimary = n.IsPrimary == "Y",
                SizeStandardMet = n.SizeStandardMet == "Y"
            })
            .ToListAsync();
    }

    public async Task<List<OrgNaicsDto>> SetNaicsAsync(int orgId, List<OrgNaicsDto> naicsCodes)
    {
        var orgExists = await _context.Organizations.AnyAsync(o => o.OrganizationId == orgId);
        if (!orgExists) throw new KeyNotFoundException($"Organization {orgId} not found.");

        // Remove existing
        var existing = await _context.OrganizationNaics
            .Where(n => n.OrganizationId == orgId)
            .ToListAsync();
        _context.OrganizationNaics.RemoveRange(existing);

        // Add new
        var entities = naicsCodes.Select(dto => new OrganizationNaics
        {
            OrganizationId = orgId,
            NaicsCode = dto.NaicsCode,
            IsPrimary = dto.IsPrimary ? "Y" : "N",
            SizeStandardMet = dto.SizeStandardMet ? "Y" : "N",
            CreatedAt = DateTime.UtcNow
        }).ToList();

        _context.OrganizationNaics.AddRange(entities);
        await _context.SaveChangesAsync();

        _logger.LogInformation("Organization {OrgId} NAICS codes updated ({Count} codes)", orgId, entities.Count);

        return entities.Select(n => new OrgNaicsDto
        {
            Id = n.Id,
            NaicsCode = n.NaicsCode,
            IsPrimary = n.IsPrimary == "Y",
            SizeStandardMet = n.SizeStandardMet == "Y"
        }).ToList();
    }

    // --- Associated NAICS (Phase 136 Unit G) ---

    public async Task<List<OrgAssociatedNaicsDto>> GetAssociatedNaicsAsync(int orgId)
    {
        return await _context.OrganizationAssociatedNaics
            .AsNoTracking()
            .Where(n => n.OrganizationId == orgId)
            .OrderBy(n => n.NaicsCode)
            .Select(n => new OrgAssociatedNaicsDto
            {
                Id = n.Id,
                NaicsCode = n.NaicsCode,
                Note = n.Note,
                CreatedAt = n.CreatedAt
            })
            .ToListAsync();
    }

    public async Task<OrgAssociatedNaicsDto> AddAssociatedNaicsAsync(int orgId, CreateAssociatedNaicsRequest request)
    {
        var orgExists = await _context.Organizations.AnyAsync(o => o.OrganizationId == orgId);
        if (!orgExists) throw new KeyNotFoundException($"Organization {orgId} not found.");

        var code = (request.NaicsCode ?? string.Empty).Trim();
        if (code.Length != 6 || !code.All(char.IsDigit))
            throw new InvalidOperationException("Associated NAICS code must be exactly 6 digits.");

        // Idempotent on (org, code) — return the existing row rather than violating the unique key.
        var existing = await _context.OrganizationAssociatedNaics
            .FirstOrDefaultAsync(n => n.OrganizationId == orgId && n.NaicsCode == code);
        if (existing != null)
        {
            return new OrgAssociatedNaicsDto
            {
                Id = existing.Id,
                NaicsCode = existing.NaicsCode,
                Note = existing.Note,
                CreatedAt = existing.CreatedAt
            };
        }

        var entity = new OrganizationAssociatedNaics
        {
            OrganizationId = orgId,
            NaicsCode = code,
            Note = string.IsNullOrWhiteSpace(request.Note) ? null : request.Note.Trim(),
            CreatedAt = DateTime.UtcNow
        };

        _context.OrganizationAssociatedNaics.Add(entity);
        await _context.SaveChangesAsync();

        _logger.LogInformation("Organization {OrgId} associated NAICS {Code} added", orgId, code);

        return new OrgAssociatedNaicsDto
        {
            Id = entity.Id,
            NaicsCode = entity.NaicsCode,
            Note = entity.Note,
            CreatedAt = entity.CreatedAt
        };
    }

    public async Task<bool> DeleteAssociatedNaicsAsync(int orgId, int id)
    {
        var entity = await _context.OrganizationAssociatedNaics
            .FirstOrDefaultAsync(n => n.Id == id && n.OrganizationId == orgId);
        if (entity == null) return false;

        _context.OrganizationAssociatedNaics.Remove(entity);
        await _context.SaveChangesAsync();

        _logger.LogInformation("Organization {OrgId} associated NAICS {Code} (id {Id}) removed", orgId, entity.NaicsCode, id);
        return true;
    }

    public async Task<List<OrgCertificationDto>> GetCertificationsAsync(int orgId)
    {
        return await _context.OrganizationCertifications
            .AsNoTracking()
            .Where(c => c.OrganizationId == orgId)
            .OrderBy(c => c.CertificationType)
            .Select(c => new OrgCertificationDto
            {
                Id = c.Id,
                CertificationType = c.CertificationType,
                CertifyingAgency = c.CertifyingAgency,
                CertificationNumber = c.CertificationNumber,
                ExpirationDate = c.ExpirationDate,
                IsActive = c.IsActive == "Y",
                Source = c.Source
            })
            .ToListAsync();
    }

    public async Task<List<OrgCertificationDto>> SetCertificationsAsync(int orgId, List<OrgCertificationDto> certifications)
    {
        var orgExists = await _context.Organizations.AnyAsync(o => o.OrganizationId == orgId);
        if (!orgExists) throw new KeyNotFoundException($"Organization {orgId} not found.");

        // Remove only MANUAL rows — leave SAM_ENTITY rows untouched
        var existing = await _context.OrganizationCertifications
            .Where(c => c.OrganizationId == orgId && c.Source == "MANUAL")
            .ToListAsync();
        _context.OrganizationCertifications.RemoveRange(existing);

        // Add new (always MANUAL source from this endpoint)
        var entities = certifications.Select(dto => new OrganizationCertification
        {
            OrganizationId = orgId,
            CertificationType = dto.CertificationType,
            CertifyingAgency = dto.CertifyingAgency,
            CertificationNumber = dto.CertificationNumber,
            ExpirationDate = dto.ExpirationDate,
            IsActive = dto.IsActive ? "Y" : "N",
            Source = "MANUAL",
            CreatedAt = DateTime.UtcNow
        }).ToList();

        _context.OrganizationCertifications.AddRange(entities);
        await _context.SaveChangesAsync();

        _logger.LogInformation("Organization {OrgId} certifications updated ({Count} manual certs)", orgId, entities.Count);

        return entities.Select(c => new OrgCertificationDto
        {
            Id = c.Id,
            CertificationType = c.CertificationType,
            CertifyingAgency = c.CertifyingAgency,
            CertificationNumber = c.CertificationNumber,
            ExpirationDate = c.ExpirationDate,
            IsActive = c.IsActive == "Y",
            Source = c.Source
        }).ToList();
    }

    public async Task<List<OrgPastPerformanceDto>> GetPastPerformancesAsync(int orgId)
    {
        return await _context.OrganizationPastPerformances
            .AsNoTracking()
            .Where(p => p.OrganizationId == orgId)
            .OrderByDescending(p => p.PeriodEnd)
            .Select(p => new OrgPastPerformanceDto
            {
                Id = p.Id,
                ContractNumber = p.ContractNumber,
                AgencyName = p.AgencyName,
                Description = p.Description,
                NaicsCode = p.NaicsCode,
                ContractValue = p.ContractValue,
                PeriodStart = p.PeriodStart,
                PeriodEnd = p.PeriodEnd,
                CreatedAt = p.CreatedAt
            })
            .ToListAsync();
    }

    public async Task<OrgPastPerformanceDto> AddPastPerformanceAsync(int orgId, CreatePastPerformanceRequest request)
    {
        var orgExists = await _context.Organizations.AnyAsync(o => o.OrganizationId == orgId);
        if (!orgExists) throw new KeyNotFoundException($"Organization {orgId} not found.");

        var entity = new OrganizationPastPerformance
        {
            OrganizationId = orgId,
            ContractNumber = request.ContractNumber,
            AgencyName = request.AgencyName,
            Description = request.Description,
            NaicsCode = request.NaicsCode,
            ContractValue = request.ContractValue,
            PeriodStart = request.PeriodStart,
            PeriodEnd = request.PeriodEnd,
            CreatedAt = DateTime.UtcNow
        };

        _context.OrganizationPastPerformances.Add(entity);
        await _context.SaveChangesAsync();

        _logger.LogInformation("Past performance {Id} added to org {OrgId}", entity.Id, orgId);

        return new OrgPastPerformanceDto
        {
            Id = entity.Id,
            ContractNumber = entity.ContractNumber,
            AgencyName = entity.AgencyName,
            Description = entity.Description,
            NaicsCode = entity.NaicsCode,
            ContractValue = entity.ContractValue,
            PeriodStart = entity.PeriodStart,
            PeriodEnd = entity.PeriodEnd,
            CreatedAt = entity.CreatedAt
        };
    }

    public async Task<bool> DeletePastPerformanceAsync(int orgId, int id)
    {
        var entity = await _context.OrganizationPastPerformances
            .FirstOrDefaultAsync(p => p.Id == id && p.OrganizationId == orgId);

        if (entity == null) return false;

        _context.OrganizationPastPerformances.Remove(entity);
        await _context.SaveChangesAsync();

        _logger.LogInformation("Past performance {Id} deleted from org {OrgId}", id, orgId);
        return true;
    }

    public async Task<List<NaicsSearchDto>> SearchNaicsAsync(string query)
    {
        if (string.IsNullOrWhiteSpace(query) || query.Length < 2)
            return new List<NaicsSearchDto>();

        return await _context.RefNaicsCodes
            .AsNoTracking()
            .Where(n => n.IsActive == "Y" &&
                       (n.NaicsCode.Contains(query) || n.Description.Contains(query)))
            .OrderBy(n => n.NaicsCode)
            .Take(50)
            .Select(n => new NaicsSearchDto
            {
                Code = n.NaicsCode,
                Title = n.Description
            })
            .ToListAsync();
    }

    public async Task<NaicsDetailDto?> GetNaicsDetailAsync(string code)
    {
        var naics = await _context.RefNaicsCodes
            .AsNoTracking()
            .FirstOrDefaultAsync(n => n.NaicsCode == code);

        if (naics == null) return null;

        var sizeStandard = await _context.RefSbaSizeStandards
            .AsNoTracking()
            .Where(s => s.NaicsCode == code)
            .OrderByDescending(s => s.EffectiveDate)
            .FirstOrDefaultAsync();

        // --- Phase 129 NAICS footnotes (Unit F) ---
        // Surface SBA size-standard footnotes/exceptions linked via the code's
        // footnote_id. A footnote_id can map to multiple sections (composite key
        // in ref_naics_footnote), so return all matching sections. Null-safe:
        // codes without a footnote_id yield an empty list.
        var footnotes = new List<NaicsFootnoteDto>();
        if (!string.IsNullOrEmpty(naics.FootnoteId))
        {
            footnotes = await _context.RefNaicsFootnotes
                .AsNoTracking()
                .Where(f => f.FootnoteId == naics.FootnoteId)
                .OrderBy(f => f.Section)
                .Select(f => new NaicsFootnoteDto
                {
                    FootnoteId = f.FootnoteId,
                    Section = f.Section,
                    Description = f.Description
                })
                .ToListAsync();
        }

        return new NaicsDetailDto
        {
            Code = naics.NaicsCode,
            Title = naics.Description,
            SizeStandard = sizeStandard?.SizeStandard,
            SizeType = sizeStandard?.SizeType,
            IndustryDescription = sizeStandard?.IndustryDescription,
            Footnotes = footnotes
        };
    }

    public Task<List<string>> GetCertificationTypesAsync()
    {
        // Static list of common federal certification types
        var types = new List<string>
        {
            "8(a)",
            "HUBZone",
            "WOSB",
            "EDWOSB",
            "SDVOSB",
            "VOSB",
            "SDB",
            "MBE",
            "WBE",
            "DBE",
            "GSA Schedule",
            "ISO 9001",
            "ISO 27001",
            "CMMI",
            "FedRAMP",
            "Other"
        };

        return Task.FromResult(types);
    }

    // --- NAICS hierarchy browsing (Phase 129 Unit B) ---

    public async Task<List<NaicsHierarchyNodeDto>> GetNaicsSectorsAsync()
    {
        return await _context.RefNaicsCodes
            .AsNoTracking()
            .Where(n => n.IsActive == "Y" && n.CodeLevel == 2)
            .OrderBy(n => n.NaicsCode)
            .Select(n => new NaicsHierarchyNodeDto
            {
                Code = n.NaicsCode,
                Title = n.Description,
                Level = n.CodeLevel,
                LevelName = n.LevelName,
                ParentCode = n.ParentCode,
                IsLeaf = n.CodeLevel == 6
            })
            .ToListAsync();
    }

    public async Task<List<NaicsHierarchyNodeDto>> GetNaicsChildrenAsync(string code)
    {
        if (string.IsNullOrWhiteSpace(code))
            return new List<NaicsHierarchyNodeDto>();

        return await _context.RefNaicsCodes
            .AsNoTracking()
            .Where(n => n.IsActive == "Y" && n.ParentCode == code)
            .OrderBy(n => n.NaicsCode)
            .Select(n => new NaicsHierarchyNodeDto
            {
                Code = n.NaicsCode,
                Title = n.Description,
                Level = n.CodeLevel,
                LevelName = n.LevelName,
                ParentCode = n.ParentCode,
                IsLeaf = n.CodeLevel == 6
            })
            .ToListAsync();
    }

    public async Task<List<NaicsHierarchyNodeDto>> GetNaicsAncestorsAsync(string code)
    {
        var chain = new List<NaicsHierarchyNodeDto>();
        if (string.IsNullOrWhiteSpace(code))
            return chain;

        // Walk up the parent_code chain. Guard against cycles / orphaned parents.
        var currentCode = code;
        var visited = new HashSet<string>();
        while (!string.IsNullOrWhiteSpace(currentCode) && visited.Add(currentCode))
        {
            var node = await _context.RefNaicsCodes
                .AsNoTracking()
                .Where(n => n.NaicsCode == currentCode)
                .Select(n => new NaicsHierarchyNodeDto
                {
                    Code = n.NaicsCode,
                    Title = n.Description,
                    Level = n.CodeLevel,
                    LevelName = n.LevelName,
                    ParentCode = n.ParentCode,
                    IsLeaf = n.CodeLevel == 6
                })
                .FirstOrDefaultAsync();

            if (node == null) break;

            chain.Add(node);
            currentCode = node.ParentCode ?? string.Empty;
        }

        // Return sector-first for breadcrumb display (we collected leaf-first).
        chain.Reverse();
        return chain;
    }

    // --- Size-eligibility engine (Phase 129 Unit B) ---

    public async Task<SizeEligibilityResultDto> CheckSizeEligibilityAsync(int orgId, string naicsCode)
    {
        var org = await _context.Organizations
            .AsNoTracking()
            .Where(o => o.OrganizationId == orgId)
            .Select(o => new { o.AnnualRevenue, o.EmployeeCount })
            .FirstOrDefaultAsync();

        var standard = await _context.RefSbaSizeStandards
            .AsNoTracking()
            .Where(s => s.NaicsCode == naicsCode)
            .OrderByDescending(s => s.EffectiveDate)
            .Select(s => new { s.SizeStandard, s.SizeType })
            .FirstOrDefaultAsync();

        return EvaluateSizeEligibility(
            naicsCode,
            standard?.SizeType,
            standard?.SizeStandard,
            org?.AnnualRevenue,
            org?.EmployeeCount,
            orgExists: org != null);
    }

    public async Task<Dictionary<string, SizeEligibilityResultDto>> CheckSizeEligibilityAsync(int orgId, IEnumerable<string> naicsCodes)
    {
        var codes = naicsCodes?
            .Where(c => !string.IsNullOrWhiteSpace(c))
            .Distinct()
            .ToList() ?? new List<string>();

        var result = new Dictionary<string, SizeEligibilityResultDto>();
        if (codes.Count == 0) return result;

        // Load the org once (avoids N+1 when annotating many opportunities).
        var org = await _context.Organizations
            .AsNoTracking()
            .Where(o => o.OrganizationId == orgId)
            .Select(o => new { o.AnnualRevenue, o.EmployeeCount })
            .FirstOrDefaultAsync();

        // Load all relevant standards in one query, then pick the latest per NAICS in memory.
        var standards = await _context.RefSbaSizeStandards
            .AsNoTracking()
            .Where(s => codes.Contains(s.NaicsCode))
            .Select(s => new { s.NaicsCode, s.SizeStandard, s.SizeType, s.EffectiveDate })
            .ToListAsync();

        var latestByCode = standards
            .GroupBy(s => s.NaicsCode)
            .ToDictionary(
                g => g.Key,
                g => g.OrderByDescending(s => s.EffectiveDate).First());

        foreach (var code in codes)
        {
            latestByCode.TryGetValue(code, out var std);
            result[code] = EvaluateSizeEligibility(
                code,
                std?.SizeType,
                std?.SizeStandard,
                org?.AnnualRevenue,
                org?.EmployeeCount,
                orgExists: org != null);
        }

        return result;
    }

    // --- Affiliation-aware size roll-up (Phase 133 Task 6, 13 CFR 121.103) ---

    public async Task<AffiliatedSizeEligibilityResultDto> CheckSizeEligibilityWithAffiliatesAsync(int orgId, string naicsCode)
    {
        var org = await _context.Organizations
            .AsNoTracking()
            .Where(o => o.OrganizationId == orgId)
            .Select(o => new { o.AnnualRevenue, o.EmployeeCount })
            .FirstOrDefaultAsync();

        var standard = await _context.RefSbaSizeStandards
            .AsNoTracking()
            .Where(s => s.NaicsCode == naicsCode)
            .OrderByDescending(s => s.EffectiveDate)
            .Select(s => new { s.SizeStandard, s.SizeType })
            .FirstOrDefaultAsync();

        // Active links for the org. SELF carries the org's OWN figures (sourced from the
        // organization row, not the link), so it does not contribute an affiliate amount and
        // is not reported as an included/excluded affiliate. Included affiliate relationships:
        // SISTER_SUBSIDIARY and JV_PARTNER (the latter excluded when mpa_approved = 'Y').
        var links = await _context.OrganizationEntities
            .AsNoTracking()
            .Where(oe => oe.OrganizationId == orgId && oe.IsActive == "Y")
            .Select(oe => new
            {
                oe.UeiSam,
                oe.Relationship,
                oe.MpaApproved,
                oe.AffiliateAnnualRevenue,
                oe.AffiliateEmployeeCount
            })
            .ToListAsync();

        var dto = new AffiliatedSizeEligibilityResultDto
        {
            NaicsCode = naicsCode,
            SizeType = standard?.SizeType,
            Threshold = standard?.SizeStandard
        };

        // Standalone (org-only) verdict reuses the existing pure evaluator.
        var standalone = EvaluateSizeEligibility(
            naicsCode,
            standard?.SizeType,
            standard?.SizeStandard,
            org?.AnnualRevenue,
            org?.EmployeeCount,
            orgExists: org != null);
        dto.StandaloneEligible = standalone.Eligible;

        if (org == null)
        {
            dto.Reason = "Organization not found.";
            return dto;
        }

        var sizeType = standard?.SizeType;
        if (string.IsNullOrWhiteSpace(sizeType) || !standard!.SizeStandard.HasValue || standard.SizeStandard.Value <= 0m)
        {
            dto.Reason = $"No SBA size standard on file for NAICS {naicsCode}; cannot roll up affiliates.";
            return dto;
        }

        var isRevenue = sizeType == "M";
        var isEmployee = sizeType == "E";
        if (!isRevenue && !isEmployee)
        {
            dto.Reason = $"Unrecognized SBA size type '{sizeType}' for NAICS {naicsCode}.";
            return dto;
        }

        // The org's own contribution (in the comparison unit). Null => the org itself lacks the figure.
        decimal? orgContribution = isRevenue
            ? (org.AnnualRevenue.HasValue ? org.AnnualRevenue.Value / 1_000_000m : (decimal?)null)
            : (org.EmployeeCount.HasValue ? org.EmployeeCount.Value : (decimal?)null);

        var includedRelationships = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        {
            "SISTER_SUBSIDIARY", "JV_PARTNER"
        };

        decimal affiliateSum = 0m;
        foreach (var link in links)
        {
            var rel = link.Relationship ?? string.Empty;

            // SELF is the hub/org's own row — already counted via the organization figures.
            if (rel.Equals("SELF", StringComparison.OrdinalIgnoreCase))
                continue;

            // TEAMING does not create affiliation under 121.103 — excluded.
            if (rel.Equals("TEAMING", StringComparison.OrdinalIgnoreCase))
            {
                dto.ExcludedAffiliates.Add(new ExcludedAffiliateDto
                {
                    Uei = link.UeiSam,
                    Relationship = rel,
                    Reason = "TEAMING"
                });
                continue;
            }

            // Any other unrecognized relationship is not an affiliation-bearing type — skip silently.
            if (!includedRelationships.Contains(rel))
                continue;

            // Approved mentor-protégé JV: the mentor's size is excluded (13 CFR 125.9(d)(1)(iii) & (d)(4)).
            if (rel.Equals("JV_PARTNER", StringComparison.OrdinalIgnoreCase)
                && string.Equals(link.MpaApproved, "Y", StringComparison.OrdinalIgnoreCase))
            {
                dto.ExcludedAffiliates.Add(new ExcludedAffiliateDto
                {
                    Uei = link.UeiSam,
                    Relationship = rel,
                    Reason = "APPROVED_MPA"
                });
                continue;
            }

            dto.AffiliateCount++;

            decimal? contribution = isRevenue
                ? (link.AffiliateAnnualRevenue.HasValue ? link.AffiliateAnnualRevenue.Value / 1_000_000m : (decimal?)null)
                : (link.AffiliateEmployeeCount.HasValue ? link.AffiliateEmployeeCount.Value : (decimal?)null);

            if (contribution.HasValue)
                affiliateSum += contribution.Value;
            else
                dto.MissingAffiliateData.Add(link.UeiSam);

            dto.IncludedAffiliates.Add(new IncludedAffiliateDto
            {
                Uei = link.UeiSam,
                Relationship = rel,
                ContributedAmount = contribution
            });
        }

        if (!orgContribution.HasValue)
        {
            // Without the org's own figure the combined total is undeterminable.
            dto.AffiliatedEligible = null;
            dto.Reason = isRevenue
                ? "Organization annual revenue not set; cannot determine combined receipts-based size."
                : "Organization employee count not set; cannot determine combined headcount-based size.";
            if (isRevenue) dto.CombinedRevenue = null; else dto.CombinedEmployees = null;
            return dto;
        }

        var combined = orgContribution.Value + affiliateSum;
        var threshold = standard.SizeStandard!.Value;
        var eligible = combined <= threshold;
        dto.AffiliatedEligible = eligible;

        if (isRevenue) dto.CombinedRevenue = combined; else dto.CombinedEmployees = combined;

        // The dangerous case: small alone, but other-than-small once affiliates are rolled in.
        dto.FlippedToOtherThanSmall = standalone.Eligible == true && !eligible;

        var unit = isRevenue ? "$M" : "employees";
        var measure = isRevenue ? "combined receipts" : "combined employees";
        var verdict = eligible ? "Small" : "Not small";
        var gapNote = dto.MissingAffiliateData.Count > 0
            ? $" ({dto.MissingAffiliateData.Count} affiliate(s) missing data — total is a lower bound)"
            : string.Empty;
        dto.Reason = $"{verdict}: {measure} {combined:0.##} {unit} vs {threshold:0.##} {unit} threshold "
            + $"(org + {dto.AffiliateCount} affiliate(s)){gapNote}.";

        return dto;
    }

    /// <summary>
    /// Pure evaluation of SBA size eligibility. No DB access, no side effects, never throws.
    /// Threshold for "M" standards is stored in $millions; org revenue is raw USD, so the
    /// threshold is converted to USD for comparison and both threshold + actual are reported
    /// in the same unit (USD millions for "M", employee count for "E").
    /// </summary>
    private static SizeEligibilityResultDto EvaluateSizeEligibility(
        string naicsCode,
        string? sizeType,
        decimal? sizeStandard,
        decimal? annualRevenue,
        int? employeeCount,
        bool orgExists)
    {
        var dto = new SizeEligibilityResultDto
        {
            NaicsCode = naicsCode,
            SizeType = sizeType,
            Eligible = null,
            Outsized = false
        };

        if (!orgExists)
        {
            dto.Reason = "Organization not found.";
            return dto;
        }

        if (string.IsNullOrWhiteSpace(sizeType) || !sizeStandard.HasValue)
        {
            dto.Reason = $"No SBA size standard on file for NAICS {naicsCode}.";
            return dto;
        }

        if (sizeType == "M")
        {
            // Receipts-based: threshold stored in $millions, org revenue in raw USD.
            dto.Threshold = sizeStandard.Value;
            dto.ThresholdUnit = "USD_MILLIONS";

            if (!annualRevenue.HasValue)
            {
                dto.Reason = "Organization annual revenue not set; cannot determine receipts-based size.";
                return dto;
            }

            var actualMillions = annualRevenue.Value / 1_000_000m;
            dto.ActualValue = actualMillions;
            ApplyComparison(dto, actualMillions, sizeStandard.Value, "annual receipts", "$M");
            return dto;
        }

        if (sizeType == "E")
        {
            // Employee-based: threshold and measure are headcounts.
            dto.Threshold = sizeStandard.Value;
            dto.ThresholdUnit = "EMPLOYEES";

            if (!employeeCount.HasValue)
            {
                dto.Reason = "Organization employee count not set; cannot determine headcount-based size.";
                return dto;
            }

            decimal actual = employeeCount.Value;
            dto.ActualValue = actual;
            ApplyComparison(dto, actual, sizeStandard.Value, "employees", "employees");
            return dto;
        }

        dto.Reason = $"Unrecognized SBA size type '{sizeType}' for NAICS {naicsCode}.";
        return dto;
    }

    private static void ApplyComparison(
        SizeEligibilityResultDto dto,
        decimal actual,
        decimal threshold,
        string measureLabel,
        string unitLabel)
    {
        var eligible = actual <= threshold;
        dto.Eligible = eligible;
        dto.Outsized = !eligible;

        if (threshold != 0m)
            dto.HeadroomPct = Math.Round((threshold - actual) / threshold * 100m, 1);

        dto.Reason = eligible
            ? $"Small: {measureLabel} {actual:0.##} {unitLabel} <= {threshold:0.##} {unitLabel} threshold."
            : $"Not small: {measureLabel} {actual:0.##} {unitLabel} exceeds {threshold:0.##} {unitLabel} threshold.";
    }

    private static OrgProfileDto MapToProfileDto(Organization org)
    {
        return new OrgProfileDto
        {
            Id = org.OrganizationId,
            Name = org.Name,
            LegalName = org.LegalName,
            DbaName = org.DbaName,
            UeiSam = org.UeiSam,
            CageCode = org.CageCode,
            Ein = org.Ein,
            AddressLine1 = org.AddressLine1,
            AddressLine2 = org.AddressLine2,
            City = org.City,
            StateCode = org.StateCode,
            ZipCode = org.ZipCode,
            CountryCode = org.CountryCode,
            Phone = org.Phone,
            Website = org.Website,
            EmployeeCount = org.EmployeeCount,
            AnnualRevenue = org.AnnualRevenue,
            FiscalYearEndMonth = org.FiscalYearEndMonth,
            EntityStructure = org.EntityStructure,
            ProfileCompleted = org.ProfileCompleted == "Y",
            ProfileCompletedAt = org.ProfileCompletedAt,
            NaicsCodes = org.NaicsCodes.Select(n => new OrgNaicsDto
            {
                Id = n.Id,
                NaicsCode = n.NaicsCode,
                IsPrimary = n.IsPrimary == "Y",
                SizeStandardMet = n.SizeStandardMet == "Y"
            }).ToList(),
            Certifications = org.Certifications.Select(c => new OrgCertificationDto
            {
                Id = c.Id,
                CertificationType = c.CertificationType,
                CertifyingAgency = c.CertifyingAgency,
                CertificationNumber = c.CertificationNumber,
                ExpirationDate = c.ExpirationDate,
                IsActive = c.IsActive == "Y",
                Source = c.Source
            }).ToList()
        };
    }
}
