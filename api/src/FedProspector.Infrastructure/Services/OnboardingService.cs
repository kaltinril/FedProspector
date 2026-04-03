using FedProspector.Core.DTOs.Onboarding;
using FedProspector.Core.Interfaces;
using FedProspector.Core.Models;
using FedProspector.Infrastructure.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;

namespace FedProspector.Infrastructure.Services;

public class OnboardingService : IOnboardingService
{
    private readonly FedProspectorDbContext _context;
    private readonly ILogger<OnboardingService> _logger;

    public OnboardingService(FedProspectorDbContext context, ILogger<OnboardingService> logger)
    {
        _context = context;
        _logger = logger;
    }

    public async Task<ProfileCompletenessDto> GetProfileCompletenessAsync(int organizationId)
    {
        var row = await _context.OrgProfileCompleteness
            .AsNoTracking()
            .FirstOrDefaultAsync(v => v.OrganizationId == organizationId);

        if (row is null)
        {
            return new ProfileCompletenessDto
            {
                OrganizationId = organizationId,
                CompletenessPct = 0,
                MissingFields = new List<string>
                {
                    "UEI", "CAGE Code", "NAICS Codes", "PSC Codes",
                    "Certifications", "Past Performance", "Address",
                    "Business Type", "Size Standard"
                }
            };
        }

        var missingFields = string.IsNullOrEmpty(row.MissingFields)
            ? new List<string>()
            : row.MissingFields.Split(", ", StringSplitOptions.RemoveEmptyEntries).ToList();

        return new ProfileCompletenessDto
        {
            OrganizationId = row.OrganizationId,
            OrganizationName = row.OrganizationName,
            CompletenessPct = row.CompletenessPct,
            HasUei = row.HasUei,
            HasCageCode = row.HasCageCode,
            HasNaics = row.HasNaics,
            HasPsc = row.HasPsc,
            HasCertifications = row.HasCertifications,
            HasPastPerformance = row.HasPastPerformance,
            HasAddress = row.HasAddress,
            HasBusinessType = row.HasBusinessType,
            HasSizeStandard = row.HasSizeStandard,
            MissingFields = missingFields
        };
    }

    public async Task<UeiImportResultDto> ImportFromUeiAsync(int organizationId, string uei)
    {
        var result = new UeiImportResultDto { Uei = uei };

        // Look up entity by UEI
        var entity = await _context.Entities
            .AsNoTracking()
            .FirstOrDefaultAsync(e => e.UeiSam == uei);

        if (entity is null)
        {
            result.EntityFound = false;
            result.Message = $"No SAM entity found for UEI {uei}";
            return result;
        }

        result.EntityFound = true;

        // Load the organization for update
        var org = await _context.Organizations.FindAsync(organizationId)
            ?? throw new KeyNotFoundException($"Organization {organizationId} not found.");

        // Populate org fields from entity (skip non-null fields - idempotent)
        var fieldsPopulated = new List<string>();

        if (string.IsNullOrEmpty(org.UeiSam))
        {
            org.UeiSam = entity.UeiSam;
            fieldsPopulated.Add("UEI");
        }

        if (string.IsNullOrEmpty(org.CageCode) && !string.IsNullOrEmpty(entity.CageCode))
        {
            org.CageCode = entity.CageCode;
            fieldsPopulated.Add("CAGE Code");
        }

        if (string.IsNullOrEmpty(org.LegalName) && !string.IsNullOrEmpty(entity.LegalBusinessName))
        {
            org.LegalName = entity.LegalBusinessName;
            fieldsPopulated.Add("Legal Name");
        }

        if (string.IsNullOrEmpty(org.DbaName) && !string.IsNullOrEmpty(entity.DbaName))
        {
            org.DbaName = entity.DbaName;
            fieldsPopulated.Add("DBA Name");
        }

        if (string.IsNullOrEmpty(org.Website) && !string.IsNullOrEmpty(entity.EntityUrl))
        {
            org.Website = entity.EntityUrl;
            fieldsPopulated.Add("Website");
        }

        if (string.IsNullOrEmpty(org.EntityStructure) && !string.IsNullOrEmpty(entity.EntityStructureCode))
        {
            org.EntityStructure = entity.EntityStructureCode;
            fieldsPopulated.Add("Business Type");
        }

        // Import address from entity_address (physical address)
        var address = await _context.EntityAddresses
            .AsNoTracking()
            .FirstOrDefaultAsync(a => a.UeiSam == uei && a.AddressType == "PHYSICAL");

        if (address is not null)
        {
            if (string.IsNullOrEmpty(org.AddressLine1) && !string.IsNullOrEmpty(address.AddressLine1))
            {
                org.AddressLine1 = address.AddressLine1;
                org.AddressLine2 = address.AddressLine2;
                org.City = address.City;
                org.StateCode = address.StateOrProvince?.Length > 2
                    ? null : address.StateOrProvince;
                org.ZipCode = address.ZipCode;
                org.CountryCode = address.CountryCode ?? "USA";
                fieldsPopulated.Add("Address");
            }
        }

        result.FieldsPopulated = fieldsPopulated;

        // Import NAICS codes (skip duplicates)
        var entityNaics = await _context.EntityNaicsCodes
            .AsNoTracking()
            .Where(n => n.UeiSam == uei)
            .ToListAsync();

        var existingNaics = await _context.OrganizationNaics
            .Where(n => n.OrganizationId == organizationId)
            .Select(n => n.NaicsCode)
            .ToListAsync();

        var naicsImported = 0;
        foreach (var en in entityNaics)
        {
            if (!existingNaics.Contains(en.NaicsCode))
            {
                _context.OrganizationNaics.Add(new OrganizationNaics
                {
                    OrganizationId = organizationId,
                    NaicsCode = en.NaicsCode,
                    IsPrimary = en.IsPrimary ?? "N",
                    SizeStandardMet = en.SbaSmallBusiness ?? "N",
                    CreatedAt = DateTime.UtcNow
                });
                naicsImported++;
            }
        }
        result.NaicsCodesImported = naicsImported;

        // Import certifications from entity_sba_certification (skip duplicates)
        var entityCerts = await _context.EntitySbaCertifications
            .AsNoTracking()
            .Where(c => c.UeiSam == uei)
            .ToListAsync();

        var existingCerts = await _context.OrganizationCertifications
            .Where(c => c.OrganizationId == organizationId)
            .Select(c => new { c.CertificationType, c.Source })
            .ToListAsync();

        var certsImported = 0;
        foreach (var ec in entityCerts)
        {
            if (!string.IsNullOrEmpty(ec.SbaTypeCode) &&
                !existingCerts.Any(c => c.CertificationType == ec.SbaTypeCode && c.Source == "SAM_GOV"))
            {
                _context.OrganizationCertifications.Add(new OrganizationCertification
                {
                    OrganizationId = organizationId,
                    CertificationType = ec.SbaTypeCode,
                    CertifyingAgency = "SBA",
                    ExpirationDate = ec.CertificationExitDate.HasValue
                        ? ec.CertificationExitDate.Value.ToDateTime(TimeOnly.MinValue)
                        : null,
                    IsActive = "Y",
                    Source = "SAM_GOV",
                    CreatedAt = DateTime.UtcNow
                });
                certsImported++;
            }
        }
        result.CertificationsImported = certsImported;

        org.UpdatedAt = DateTime.UtcNow;
        await _context.SaveChangesAsync();

        var parts = new List<string>();
        if (fieldsPopulated.Count > 0) parts.Add($"Fields: {string.Join(", ", fieldsPopulated)}");
        if (naicsImported > 0) parts.Add($"{naicsImported} NAICS codes");
        if (certsImported > 0) parts.Add($"{certsImported} certifications");
        result.Message = parts.Count > 0
            ? $"Imported: {string.Join("; ", parts)}"
            : "Entity found but nothing new to import (all fields already populated)";

        _logger.LogInformation("UEI import for org {OrgId} from {Uei}: {Message}",
            organizationId, uei, result.Message);

        return result;
    }

    public async Task<List<CertificationAlertDto>> GetCertificationAlertsAsync(int organizationId)
    {
        return await _context.CertificationExpirationAlerts
            .AsNoTracking()
            .Where(v => v.OrganizationId == organizationId)
            .OrderBy(v => v.DaysUntilExpiration)
            .Select(v => new CertificationAlertDto
            {
                CertificationType = v.CertificationType,
                ExpirationDate = v.ExpirationDate,
                DaysUntilExpiration = v.DaysUntilExpiration,
                AlertLevel = v.AlertLevel,
                Source = v.Source
            })
            .ToListAsync();
    }

    public async Task<List<SizeStandardAlertDto>> GetSizeStandardAlertsAsync(int organizationId)
    {
        return await _context.SbaSizeStandardMonitors
            .AsNoTracking()
            .Where(v => v.OrganizationId == organizationId)
            .OrderByDescending(v => v.PctOfThreshold)
            .Select(v => new SizeStandardAlertDto
            {
                NaicsCode = v.NaicsCode,
                SizeStandardType = v.SizeStandardType,
                Threshold = v.Threshold,
                CurrentValue = v.CurrentValue,
                PctOfThreshold = v.PctOfThreshold
            })
            .ToListAsync();
    }

    public async Task<List<PastPerformanceRelevanceDto>> GetPastPerformanceRelevanceAsync(
        int organizationId, string? noticeId)
    {
        var query = _context.PastPerformanceRelevance
            .AsNoTracking()
            .Where(v => v.OrganizationId == organizationId);

        if (!string.IsNullOrWhiteSpace(noticeId))
            query = query.Where(v => v.NoticeId == noticeId);

        return await query
            .OrderByDescending(v => v.RelevanceScore)
            .Take(100)
            .Select(v => new PastPerformanceRelevanceDto
            {
                PastPerformanceId = v.PastPerformanceId,
                ContractNumber = v.ContractNumber,
                PpAgency = v.PpAgency,
                PpNaics = v.PpNaics,
                PpValue = v.PpValue,
                NoticeId = v.NoticeId,
                OpportunityTitle = v.OpportunityTitle,
                OppAgency = v.OppAgency,
                OppNaics = v.OppNaics,
                OppValue = v.OppValue,
                NaicsMatch = v.NaicsMatch,
                AgencyMatch = v.AgencyMatch,
                ValueSimilarity = v.ValueSimilarity,
                YearsSinceCompletion = v.YearsSinceCompletion,
                RelevanceScore = v.RelevanceScore
            })
            .ToListAsync();
    }

    public async Task<List<PortfolioGapDto>> GetPortfolioGapsAsync(int organizationId)
    {
        return await _context.PortfolioGapAnalysis
            .AsNoTracking()
            .Where(v => v.OrganizationId == organizationId)
            .OrderBy(v => v.GapType)
            .ThenByDescending(v => v.OpportunityCount)
            .Select(v => new PortfolioGapDto
            {
                NaicsCode = v.NaicsCode,
                OpportunityCount = v.OpportunityCount,
                PastPerformanceCount = v.PastPerformanceCount,
                GapType = v.GapType
            })
            .ToListAsync();
    }

    public async Task<OrganizationPscDto> AddPscCodeAsync(int organizationId, string pscCode)
    {
        // Check for duplicate
        var exists = await _context.OrganizationPscs
            .AnyAsync(p => p.OrganizationId == organizationId && p.PscCode == pscCode);

        if (exists)
            throw new InvalidOperationException($"PSC code {pscCode} already exists for this organization.");

        var psc = new OrganizationPsc
        {
            OrganizationId = organizationId,
            PscCode = pscCode,
            AddedAt = DateTime.UtcNow
        };

        _context.OrganizationPscs.Add(psc);
        await _context.SaveChangesAsync();

        _logger.LogInformation("PSC code {PscCode} added to org {OrgId}", pscCode, organizationId);

        return new OrganizationPscDto
        {
            OrganizationPscId = psc.OrganizationPscId,
            PscCode = psc.PscCode,
            AddedAt = psc.AddedAt
        };
    }

    public async Task<bool> RemovePscCodeAsync(int organizationId, int pscId)
    {
        var psc = await _context.OrganizationPscs
            .FirstOrDefaultAsync(p => p.OrganizationPscId == pscId && p.OrganizationId == organizationId);

        if (psc is null) return false;

        _context.OrganizationPscs.Remove(psc);
        await _context.SaveChangesAsync();

        _logger.LogInformation("PSC code {PscCode} (id {PscId}) removed from org {OrgId}",
            psc.PscCode, pscId, organizationId);

        return true;
    }

    public async Task<List<OrganizationPscDto>> GetPscCodesAsync(int organizationId)
    {
        return await _context.OrganizationPscs
            .AsNoTracking()
            .Where(p => p.OrganizationId == organizationId)
            .OrderBy(p => p.PscCode)
            .Select(p => new OrganizationPscDto
            {
                OrganizationPscId = p.OrganizationPscId,
                PscCode = p.PscCode,
                AddedAt = p.AddedAt
            })
            .ToListAsync();
    }
}
