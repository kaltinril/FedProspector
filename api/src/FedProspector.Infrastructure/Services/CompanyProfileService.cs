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
                IsActive = c.IsActive == "Y"
            })
            .ToListAsync();
    }

    public async Task<List<OrgCertificationDto>> SetCertificationsAsync(int orgId, List<OrgCertificationDto> certifications)
    {
        var orgExists = await _context.Organizations.AnyAsync(o => o.OrganizationId == orgId);
        if (!orgExists) throw new KeyNotFoundException($"Organization {orgId} not found.");

        // Remove existing
        var existing = await _context.OrganizationCertifications
            .Where(c => c.OrganizationId == orgId)
            .ToListAsync();
        _context.OrganizationCertifications.RemoveRange(existing);

        // Add new
        var entities = certifications.Select(dto => new OrganizationCertification
        {
            OrganizationId = orgId,
            CertificationType = dto.CertificationType,
            CertifyingAgency = dto.CertifyingAgency,
            CertificationNumber = dto.CertificationNumber,
            ExpirationDate = dto.ExpirationDate,
            IsActive = dto.IsActive ? "Y" : "N",
            CreatedAt = DateTime.UtcNow
        }).ToList();

        _context.OrganizationCertifications.AddRange(entities);
        await _context.SaveChangesAsync();

        _logger.LogInformation("Organization {OrgId} certifications updated ({Count} certs)", orgId, entities.Count);

        return entities.Select(c => new OrgCertificationDto
        {
            Id = c.Id,
            CertificationType = c.CertificationType,
            CertifyingAgency = c.CertifyingAgency,
            CertificationNumber = c.CertificationNumber,
            ExpirationDate = c.ExpirationDate,
            IsActive = c.IsActive == "Y"
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

        return new NaicsDetailDto
        {
            Code = naics.NaicsCode,
            Title = naics.Description,
            SizeStandard = sizeStandard?.SizeStandard,
            SizeType = sizeStandard?.SizeType,
            IndustryDescription = sizeStandard?.IndustryDescription
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
                IsActive = c.IsActive == "Y"
            }).ToList()
        };
    }
}
