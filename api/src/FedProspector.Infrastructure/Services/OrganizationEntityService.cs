using FedProspector.Core.DTOs.Organizations;
using FedProspector.Core.Interfaces;
using FedProspector.Core.Models;
using FedProspector.Infrastructure.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;

namespace FedProspector.Infrastructure.Services;

public class OrganizationEntityService : IOrganizationEntityService
{
    private readonly FedProspectorDbContext _context;
    private readonly ILogger<OrganizationEntityService> _logger;

    private static readonly HashSet<string> ValidRelationships = new(StringComparer.OrdinalIgnoreCase)
    {
        "SELF", "JV_PARTNER", "TEAMING"
    };

    public OrganizationEntityService(
        FedProspectorDbContext context,
        ILogger<OrganizationEntityService> logger)
    {
        _context = context;
        _logger = logger;
    }

    public async Task<List<OrganizationEntityDto>> GetLinkedEntitiesAsync(int orgId)
    {
        var links = await _context.OrganizationEntities
            .AsNoTracking()
            .Include(oe => oe.Entity)
            .Include(oe => oe.AddedByUser)
            .Where(oe => oe.OrganizationId == orgId && oe.IsActive == "Y")
            .OrderBy(oe => oe.Relationship)
            .ThenBy(oe => oe.CreatedAt)
            .ToListAsync();

        var result = new List<OrganizationEntityDto>();
        foreach (var link in links)
        {
            var dto = MapToDto(link);

            // Get NAICS and cert counts
            if (link.Entity != null)
            {
                dto.NaicsCount = await _context.EntityNaicsCodes
                    .AsNoTracking()
                    .CountAsync(n => n.UeiSam == link.UeiSam);

                var todayForCount = DateOnly.FromDateTime(DateTime.UtcNow);
                var sbaCount = await _context.EntitySbaCertifications.AsNoTracking()
                    .CountAsync(c => c.UeiSam == link.UeiSam
                        && (c.CertificationExitDate == null || c.CertificationExitDate > todayForCount));

                var relevantBtCodes = new[] { "8W", "8E", "8C", "8D", "QF", "A5" };
                var btCount = await _context.EntityBusinessTypes.AsNoTracking()
                    .CountAsync(bt => bt.UeiSam == link.UeiSam && relevantBtCodes.Contains(bt.BusinessTypeCode));

                dto.CertificationCount = sbaCount + btCount;
            }

            result.Add(dto);
        }

        return result;
    }

    public async Task<OrganizationEntityDto> LinkEntityAsync(int orgId, int userId, LinkEntityRequest request)
    {
        var relationship = request.Relationship.ToUpperInvariant();
        if (!ValidRelationships.Contains(relationship))
            throw new InvalidOperationException($"Invalid relationship type: {request.Relationship}. Valid types: {string.Join(", ", ValidRelationships)}");

        // Verify entity exists
        var entity = await _context.Entities.AsNoTracking()
            .FirstOrDefaultAsync(e => e.UeiSam == request.UeiSam)
            ?? throw new KeyNotFoundException($"Entity with UEI {request.UeiSam} not found. Load the entity first via SAM.gov.");

        // Check for existing active link with same relationship
        var existing = await _context.OrganizationEntities
            .FirstOrDefaultAsync(oe => oe.OrganizationId == orgId
                && oe.UeiSam == request.UeiSam
                && oe.Relationship == relationship);

        if (existing != null)
        {
            if (existing.IsActive == "Y")
                throw new InvalidOperationException($"Entity {request.UeiSam} is already linked as {relationship}.");

            // Reactivate
            existing.IsActive = "Y";
            existing.PartnerUei = request.PartnerUei;
            existing.Notes = request.Notes;
            existing.AddedBy = userId;
            existing.UpdatedAt = DateTime.UtcNow;
            await _context.SaveChangesAsync();

            _logger.LogInformation("Reactivated entity link {UeiSam} ({Relationship}) for org {OrgId}",
                request.UeiSam, relationship, orgId);

            // Sync certs after reactivation (profile + NAICS for SELF)
            if (relationship == "SELF")
                await PopulateFromSelfEntityAsync(orgId, request.UeiSam);
            else
                await SyncEntityCertsAsync(orgId);

            return await GetSingleDtoAsync(existing);
        }

        // Only one SELF entity allowed
        if (relationship == "SELF")
        {
            var existingSelf = await _context.OrganizationEntities
                .AnyAsync(oe => oe.OrganizationId == orgId && oe.Relationship == "SELF" && oe.IsActive == "Y");
            if (existingSelf)
                throw new InvalidOperationException("Organization already has a SELF entity linked. Deactivate the existing one first.");
        }

        var link = new OrganizationEntity
        {
            OrganizationId = orgId,
            UeiSam = request.UeiSam,
            PartnerUei = request.PartnerUei,
            Relationship = relationship,
            IsActive = "Y",
            AddedBy = userId,
            Notes = request.Notes,
            CreatedAt = DateTime.UtcNow,
            UpdatedAt = DateTime.UtcNow
        };

        _context.OrganizationEntities.Add(link);
        await _context.SaveChangesAsync();

        _logger.LogInformation("Linked entity {UeiSam} ({Relationship}) to org {OrgId}",
            request.UeiSam, relationship, orgId);

        // If linking SELF entity, auto-populate org profile (fields + NAICS)
        if (relationship == "SELF")
        {
            await PopulateFromSelfEntityAsync(orgId, request.UeiSam);
        }
        else
        {
            // For non-SELF links, still sync certs from all linked entities
            await SyncEntityCertsAsync(orgId);
        }

        return await GetSingleDtoAsync(link);
    }

    public async Task DeactivateLinkAsync(int orgId, int linkId)
    {
        var link = await _context.OrganizationEntities
            .FirstOrDefaultAsync(oe => oe.Id == linkId && oe.OrganizationId == orgId)
            ?? throw new KeyNotFoundException($"Entity link {linkId} not found.");

        var wasSelf = link.Relationship == "SELF";

        link.IsActive = "N";
        link.UpdatedAt = DateTime.UtcNow;
        await _context.SaveChangesAsync();

        _logger.LogInformation("Deactivated entity link {LinkId} ({UeiSam} / {Relationship}) for org {OrgId}",
            linkId, link.UeiSam, link.Relationship, orgId);

        // If SELF entity was delinked, clear the UeiSam on the org
        if (wasSelf)
        {
            var org = await _context.Organizations.FindAsync(orgId);
            if (org != null)
            {
                org.UeiSam = null;
                org.UpdatedAt = DateTime.UtcNow;
                await _context.SaveChangesAsync();
            }
        }

        // Re-sync certs from remaining active entities
        await SyncEntityCertsAsync(orgId);
    }

    /// <summary>
    /// Re-copy NAICS, certifications, and profile fields from the SELF entity.
    /// </summary>
    public async Task<RefreshSelfEntityResponse> RefreshFromSelfEntityAsync(int orgId)
    {
        var selfLink = await _context.OrganizationEntities
            .AsNoTracking()
            .FirstOrDefaultAsync(oe => oe.OrganizationId == orgId && oe.Relationship == "SELF" && oe.IsActive == "Y")
            ?? throw new InvalidOperationException("No SELF entity is linked to this organization.");

        var result = await PopulateFromSelfEntityAsync(orgId, selfLink.UeiSam);
        return result;
    }

    /// <summary>
    /// Compute effective NAICS codes: union of organization_naics + entity_naics for all active linked entities.
    /// </summary>
    public async Task<List<string>> GetAggregateNaicsAsync(int orgId)
    {
        // Manual org NAICS (always included)
        var orgNaics = await _context.OrganizationNaics
            .AsNoTracking()
            .Where(n => n.OrganizationId == orgId)
            .Select(n => n.NaicsCode)
            .ToListAsync();

        // Entity NAICS from all active linked entities
        var linkedUeis = await _context.OrganizationEntities
            .AsNoTracking()
            .Where(oe => oe.OrganizationId == orgId && oe.IsActive == "Y")
            .Select(oe => oe.UeiSam)
            .ToListAsync();

        if (linkedUeis.Count > 0)
        {
            var entityNaics = await _context.EntityNaicsCodes
                .AsNoTracking()
                .Where(en => linkedUeis.Contains(en.UeiSam))
                .Select(en => en.NaicsCode)
                .ToListAsync();

            orgNaics.AddRange(entityNaics);
        }

        return orgNaics.Distinct().OrderBy(n => n).ToList();
    }

    /// <summary>
    /// Get all active linked entity UEIs for this organization.
    /// </summary>
    public async Task<List<string>> GetLinkedUeisAsync(int orgId)
    {
        var entities = await _context.OrganizationEntities
            .AsNoTracking()
            .Where(oe => oe.OrganizationId == orgId && oe.IsActive == "Y")
            .Select(oe => new { oe.UeiSam, oe.PartnerUei })
            .ToListAsync();

        return entities
            .SelectMany(oe => new[] { oe.UeiSam, oe.PartnerUei })
            .Where(u => !string.IsNullOrEmpty(u))
            .Distinct()
            .ToList()!;
    }

    /// <summary>
    /// Sync certifications from all active linked entities into organization_certification.
    /// Deletes existing SAM_ENTITY rows and re-inserts from entity_business_type + entity_sba_certification.
    /// </summary>
    public async Task<int> SyncEntityCertsAsync(int orgId)
    {
        // 1. Get all active linked UEIs
        var linkedUeis = await GetLinkedUeisAsync(orgId);
        if (!linkedUeis.Any())
        {
            // No linked entities — remove all SAM_ENTITY certs
            var stale = await _context.OrganizationCertifications
                .Where(c => c.OrganizationId == orgId && c.Source == "SAM_ENTITY")
                .ToListAsync();
            _context.OrganizationCertifications.RemoveRange(stale);
            await _context.SaveChangesAsync();
            return 0;
        }

        // 2. Query entity_business_type for all linked UEIs
        var businessTypes = await _context.EntityBusinessTypes.AsNoTracking()
            .Where(bt => linkedUeis.Contains(bt.UeiSam))
            .Select(bt => bt.BusinessTypeCode)
            .ToListAsync();

        // 3. Query entity_sba_certification for all linked UEIs (active only)
        var today = DateOnly.FromDateTime(DateTime.UtcNow);
        var sbaCerts = await _context.EntitySbaCertifications.AsNoTracking()
            .Where(c => linkedUeis.Contains(c.UeiSam)
                && (c.CertificationExitDate == null || c.CertificationExitDate > today))
            .ToListAsync();

        // 4. Map to CertificationType values
        var certTypes = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        // Business type mapping
        var btMap = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
        {
            ["8W"] = "WOSB",
            ["8C"] = "WOSB",
            ["8E"] = "EDWOSB",
            ["8D"] = "EDWOSB",
            ["QF"] = "SDVOSB",
            ["A5"] = "VOSB",
        };

        foreach (var code in businessTypes)
        {
            if (btMap.TryGetValue(code, out var certType))
                certTypes.Add(certType);
        }

        // SBA cert mapping
        var sbaMap = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
        {
            ["A4"] = "8(a)",
            ["A6"] = "8(a)",
            ["XX"] = "HUBZone",
        };

        foreach (var cert in sbaCerts)
        {
            if (cert.SbaTypeCode != null && sbaMap.TryGetValue(cert.SbaTypeCode, out var certType))
                certTypes.Add(certType);
        }

        // General rule: any small-business-related code -> SDB
        if (certTypes.Any())
            certTypes.Add("SDB");

        // 5. Delete existing SAM_ENTITY rows, insert new ones
        var existing = await _context.OrganizationCertifications
            .Where(c => c.OrganizationId == orgId && c.Source == "SAM_ENTITY")
            .ToListAsync();
        _context.OrganizationCertifications.RemoveRange(existing);

        foreach (var ct in certTypes)
        {
            // Find the best SBA cert for expiration date (if applicable)
            EntitySbaCertification? matchingSba = null;
            if (ct == "8(a)")
                matchingSba = sbaCerts.FirstOrDefault(c => c.SbaTypeCode == "A4" || c.SbaTypeCode == "A6");
            else if (ct == "HUBZone")
                matchingSba = sbaCerts.FirstOrDefault(c => c.SbaTypeCode == "XX");

            _context.OrganizationCertifications.Add(new OrganizationCertification
            {
                OrganizationId = orgId,
                CertificationType = ct,
                CertifyingAgency = "SAM.gov",
                CertificationNumber = null,
                ExpirationDate = matchingSba?.CertificationExitDate.HasValue == true
                    ? matchingSba.CertificationExitDate.Value.ToDateTime(TimeOnly.MinValue)
                    : null,
                IsActive = "Y",
                Source = "SAM_ENTITY",
                CreatedAt = DateTime.UtcNow
            });
        }

        await _context.SaveChangesAsync();
        _logger.LogInformation("Synced {CertCount} certifications from linked entities for org {OrgId}",
            certTypes.Count, orgId);
        return certTypes.Count;
    }

    /// <summary>
    /// Re-sync certifications for all organizations that have active linked entities.
    /// </summary>
    public async Task<int> ResyncAllOrgsAsync()
    {
        var orgIds = await _context.OrganizationEntities
            .Where(oe => oe.IsActive == "Y")
            .Select(oe => oe.OrganizationId)
            .Distinct()
            .ToListAsync();

        int total = 0;
        foreach (var orgId in orgIds)
        {
            total += await SyncEntityCertsAsync(orgId);
        }
        return total;
    }

    // -----------------------------------------------------------------------
    // Private helpers
    // -----------------------------------------------------------------------

    private async Task<RefreshSelfEntityResponse> PopulateFromSelfEntityAsync(int orgId, string ueiSam)
    {
        var entity = await _context.Entities.AsNoTracking()
            .FirstOrDefaultAsync(e => e.UeiSam == ueiSam);

        if (entity == null)
            return new RefreshSelfEntityResponse { Message = "Entity not found." };

        var org = await _context.Organizations.FindAsync(orgId);
        if (org == null)
            return new RefreshSelfEntityResponse { Message = "Organization not found." };

        // Update org profile fields from entity
        org.UeiSam = ueiSam;
        org.LegalName = entity.LegalBusinessName;
        org.DbaName = entity.DbaName;
        org.CageCode = entity.CageCode;
        org.Website = entity.EntityUrl;
        org.EntityStructure = entity.EntityStructureCode;
        org.UpdatedAt = DateTime.UtcNow;

        // Copy address from entity's physical address
        var address = await _context.EntityAddresses.AsNoTracking()
            .FirstOrDefaultAsync(a => a.UeiSam == ueiSam && a.AddressType == "physical");
        if (address != null)
        {
            org.AddressLine1 = address.AddressLine1;
            org.AddressLine2 = address.AddressLine2;
            org.City = address.City;
            org.StateCode = address.StateOrProvince;
            org.ZipCode = address.ZipCode;
            org.CountryCode = address.CountryCode;
        }

        await _context.SaveChangesAsync();

        // Copy NAICS codes from entity_naics
        var entityNaics = await _context.EntityNaicsCodes.AsNoTracking()
            .Where(n => n.UeiSam == ueiSam)
            .ToListAsync();

        // Remove existing org NAICS and replace
        var existingNaics = await _context.OrganizationNaics
            .Where(n => n.OrganizationId == orgId)
            .ToListAsync();
        _context.OrganizationNaics.RemoveRange(existingNaics);

        foreach (var en in entityNaics)
        {
            _context.OrganizationNaics.Add(new OrganizationNaics
            {
                OrganizationId = orgId,
                NaicsCode = en.NaicsCode,
                IsPrimary = en.IsPrimary ?? "N",
                SizeStandardMet = en.SbaSmallBusiness ?? "N",
                CreatedAt = DateTime.UtcNow
            });
        }

        await _context.SaveChangesAsync();

        // Sync certifications from ALL linked entities (not just SELF)
        var certCount = await SyncEntityCertsAsync(orgId);

        _logger.LogInformation(
            "Populated org {OrgId} from SELF entity {UeiSam}: {NaicsCount} NAICS, {CertCount} certs",
            orgId, ueiSam, entityNaics.Count, certCount);

        return new RefreshSelfEntityResponse
        {
            NaicsCopied = entityNaics.Count,
            CertificationsCopied = certCount,
            ProfileUpdated = true,
            Message = $"Copied {entityNaics.Count} NAICS codes, {certCount} certifications, and profile fields from {entity.LegalBusinessName}."
        };
    }

    private async Task<OrganizationEntityDto> GetSingleDtoAsync(OrganizationEntity link)
    {
        // Reload with navigation properties
        var loaded = await _context.OrganizationEntities
            .AsNoTracking()
            .Include(oe => oe.Entity)
            .Include(oe => oe.AddedByUser)
            .FirstAsync(oe => oe.Id == link.Id);

        var dto = MapToDto(loaded);
        dto.NaicsCount = await _context.EntityNaicsCodes.AsNoTracking()
            .CountAsync(n => n.UeiSam == link.UeiSam);

        var todayForDto = DateOnly.FromDateTime(DateTime.UtcNow);
        var sbaCountDto = await _context.EntitySbaCertifications.AsNoTracking()
            .CountAsync(c => c.UeiSam == link.UeiSam
                && (c.CertificationExitDate == null || c.CertificationExitDate > todayForDto));

        var relevantBtCodesDto = new[] { "8W", "8E", "8C", "8D", "QF", "A5" };
        var btCountDto = await _context.EntityBusinessTypes.AsNoTracking()
            .CountAsync(bt => bt.UeiSam == link.UeiSam && relevantBtCodesDto.Contains(bt.BusinessTypeCode));

        dto.CertificationCount = sbaCountDto + btCountDto;

        return dto;
    }

    private static OrganizationEntityDto MapToDto(OrganizationEntity link)
    {
        return new OrganizationEntityDto
        {
            Id = link.Id,
            UeiSam = link.UeiSam,
            PartnerUei = link.PartnerUei,
            Relationship = link.Relationship,
            IsActive = link.IsActive == "Y",
            Notes = link.Notes,
            AddedByName = link.AddedByUser?.DisplayName,
            CreatedAt = link.CreatedAt,
            LegalBusinessName = link.Entity?.LegalBusinessName,
            DbaName = link.Entity?.DbaName,
            CageCode = link.Entity?.CageCode,
            RegistrationStatus = link.Entity?.RegistrationStatus,
            PrimaryNaics = link.Entity?.PrimaryNaics,
        };
    }
}
