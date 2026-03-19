using FedProspector.Core.DTOs.Organizations;
using FedProspector.Core.Models;
using FedProspector.Infrastructure.Data;
using FedProspector.Infrastructure.Services;
using FluentAssertions;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging.Abstractions;

namespace FedProspector.Infrastructure.Tests.Services;

public class OrganizationEntityServiceTests : IDisposable
{
    private readonly FedProspectorDbContext _context;
    private readonly OrganizationEntityService _service;

    public OrganizationEntityServiceTests()
    {
        var options = new DbContextOptionsBuilder<FedProspectorDbContext>()
            .UseInMemoryDatabase(databaseName: Guid.NewGuid().ToString())
            .Options;

        _context = new FedProspectorDbContext(options);
        _service = new OrganizationEntityService(_context, NullLogger<OrganizationEntityService>.Instance);
    }

    public void Dispose()
    {
        _context.Dispose();
    }

    // -----------------------------------------------------------------------
    // Seed helpers
    // -----------------------------------------------------------------------

    private Organization SeedOrganization(int orgId = 1, string name = "Test Org")
    {
        var org = new Organization
        {
            OrganizationId = orgId,
            Name = name,
            Slug = "test-org",
            IsActive = "Y",
            MaxUsers = 10,
            SubscriptionTier = "trial",
            CreatedAt = DateTime.UtcNow,
            UpdatedAt = DateTime.UtcNow
        };
        _context.Organizations.Add(org);
        _context.SaveChanges();
        return org;
    }

    private AppUser SeedUser(int orgId = 1)
    {
        var user = new AppUser
        {
            OrganizationId = orgId,
            Username = "testuser",
            DisplayName = "Test User",
            Email = "test@example.com",
            PasswordHash = "hash",
            Role = "USER",
            OrgRole = "member",
            IsActive = "Y",
            IsOrgAdmin = "N",
            MfaEnabled = "N",
            ForcePasswordChange = "N",
            FailedLoginAttempts = 0,
            CreatedAt = DateTime.UtcNow
        };
        _context.AppUsers.Add(user);
        _context.SaveChanges();
        return user;
    }

    private Entity SeedEntity(string uei, string legalName = "Test Company")
    {
        var entity = new Entity
        {
            UeiSam = uei,
            LegalBusinessName = legalName,
            RegistrationStatus = "A",
            PrimaryNaics = "541512"
        };
        _context.Entities.Add(entity);
        _context.SaveChanges();
        return entity;
    }

    private void SeedBusinessType(string uei, string code)
    {
        _context.EntityBusinessTypes.Add(new EntityBusinessType
        {
            UeiSam = uei,
            BusinessTypeCode = code
        });
        _context.SaveChanges();
    }

    private void SeedSbaCert(string uei, string sbaTypeCode, DateOnly? exitDate = null, string? desc = null)
    {
        _context.EntitySbaCertifications.Add(new EntitySbaCertification
        {
            UeiSam = uei,
            SbaTypeCode = sbaTypeCode,
            SbaTypeDesc = desc ?? $"SBA {sbaTypeCode}",
            CertificationEntryDate = DateOnly.FromDateTime(DateTime.UtcNow.AddYears(-1)),
            CertificationExitDate = exitDate
        });
        _context.SaveChanges();
    }

    private OrganizationEntity SeedLink(int orgId, string uei, string relationship, bool active = true)
    {
        var link = new OrganizationEntity
        {
            OrganizationId = orgId,
            UeiSam = uei,
            Relationship = relationship,
            IsActive = active ? "Y" : "N",
            CreatedAt = DateTime.UtcNow,
            UpdatedAt = DateTime.UtcNow
        };
        _context.OrganizationEntities.Add(link);
        _context.SaveChanges();
        return link;
    }

    private void SeedManualCert(int orgId, string certType)
    {
        _context.OrganizationCertifications.Add(new OrganizationCertification
        {
            OrganizationId = orgId,
            CertificationType = certType,
            CertifyingAgency = "Manual",
            IsActive = "Y",
            Source = "MANUAL",
            CreatedAt = DateTime.UtcNow
        });
        _context.SaveChanges();
    }

    private void SeedSamEntityCert(int orgId, string certType)
    {
        _context.OrganizationCertifications.Add(new OrganizationCertification
        {
            OrganizationId = orgId,
            CertificationType = certType,
            CertifyingAgency = "SAM.gov",
            IsActive = "Y",
            Source = "SAM_ENTITY",
            CreatedAt = DateTime.UtcNow
        });
        _context.SaveChanges();
    }

    private List<OrganizationCertification> GetCerts(int orgId) =>
        _context.OrganizationCertifications
            .Where(c => c.OrganizationId == orgId)
            .OrderBy(c => c.CertificationType)
            .ToList();

    // =======================================================================
    // SyncEntityCertsAsync — Business Type Mapping
    // =======================================================================

    [Fact]
    public async Task SyncEntityCerts_BusinessType8W_MapsToWOSB()
    {
        SeedOrganization();
        SeedEntity("UEI000000001");
        SeedBusinessType("UEI000000001", "8W");
        SeedLink(1, "UEI000000001", "SELF");

        await _service.SyncEntityCertsAsync(1);

        var certs = GetCerts(1);
        certs.Should().Contain(c => c.CertificationType == "WOSB");
    }

    [Fact]
    public async Task SyncEntityCerts_BusinessType8E_MapsToEDWOSB()
    {
        SeedOrganization();
        SeedEntity("UEI000000001");
        SeedBusinessType("UEI000000001", "8E");
        SeedLink(1, "UEI000000001", "SELF");

        await _service.SyncEntityCertsAsync(1);

        var certs = GetCerts(1);
        certs.Should().Contain(c => c.CertificationType == "EDWOSB");
    }

    [Fact]
    public async Task SyncEntityCerts_BusinessType8C_MapsToWOSB_DedupWith8W()
    {
        SeedOrganization();
        SeedEntity("UEI000000001");
        SeedBusinessType("UEI000000001", "8W");
        SeedBusinessType("UEI000000001", "8C");
        SeedLink(1, "UEI000000001", "SELF");

        await _service.SyncEntityCertsAsync(1);

        var certs = GetCerts(1);
        certs.Count(c => c.CertificationType == "WOSB").Should().Be(1,
            "8W and 8C both map to WOSB but should be deduplicated");
    }

    [Fact]
    public async Task SyncEntityCerts_BusinessType8D_MapsToEDWOSB()
    {
        SeedOrganization();
        SeedEntity("UEI000000001");
        SeedBusinessType("UEI000000001", "8D");
        SeedLink(1, "UEI000000001", "SELF");

        await _service.SyncEntityCertsAsync(1);

        var certs = GetCerts(1);
        certs.Should().Contain(c => c.CertificationType == "EDWOSB");
    }

    [Fact]
    public async Task SyncEntityCerts_BusinessTypeQF_MapsToSDVOSB()
    {
        SeedOrganization();
        SeedEntity("UEI000000001");
        SeedBusinessType("UEI000000001", "QF");
        SeedLink(1, "UEI000000001", "SELF");

        await _service.SyncEntityCertsAsync(1);

        var certs = GetCerts(1);
        certs.Should().Contain(c => c.CertificationType == "SDVOSB");
    }

    [Fact]
    public async Task SyncEntityCerts_BusinessTypeA5_MapsToVOSB()
    {
        SeedOrganization();
        SeedEntity("UEI000000001");
        SeedBusinessType("UEI000000001", "A5");
        SeedLink(1, "UEI000000001", "SELF");

        await _service.SyncEntityCertsAsync(1);

        var certs = GetCerts(1);
        certs.Should().Contain(c => c.CertificationType == "VOSB");
    }

    // =======================================================================
    // SyncEntityCertsAsync — SBA Certification Mapping
    // =======================================================================

    [Fact]
    public async Task SyncEntityCerts_SbaA4_ActiveNoExitDate_MapsTo8a()
    {
        SeedOrganization();
        SeedEntity("UEI000000001");
        SeedSbaCert("UEI000000001", "A4", exitDate: null);
        SeedLink(1, "UEI000000001", "SELF");

        await _service.SyncEntityCertsAsync(1);

        var certs = GetCerts(1);
        certs.Should().Contain(c => c.CertificationType == "8(a)");
    }

    [Fact]
    public async Task SyncEntityCerts_SbaA4_ExpiredExitDate_DoesNotProduce8a()
    {
        SeedOrganization();
        SeedEntity("UEI000000001");
        var pastDate = DateOnly.FromDateTime(DateTime.UtcNow.AddDays(-30));
        SeedSbaCert("UEI000000001", "A4", exitDate: pastDate);
        SeedLink(1, "UEI000000001", "SELF");

        await _service.SyncEntityCertsAsync(1);

        var certs = GetCerts(1);
        certs.Should().NotContain(c => c.CertificationType == "8(a)",
            "expired SBA cert should not produce a certification");
    }

    [Fact]
    public async Task SyncEntityCerts_SbaA4_FutureExitDate_MapsTo8a()
    {
        SeedOrganization();
        SeedEntity("UEI000000001");
        var futureDate = DateOnly.FromDateTime(DateTime.UtcNow.AddYears(2));
        SeedSbaCert("UEI000000001", "A4", exitDate: futureDate);
        SeedLink(1, "UEI000000001", "SELF");

        await _service.SyncEntityCertsAsync(1);

        var certs = GetCerts(1);
        certs.Should().Contain(c => c.CertificationType == "8(a)");
        var eightA = certs.First(c => c.CertificationType == "8(a)");
        eightA.ExpirationDate.Should().NotBeNull("future exit date should be set on the cert");
    }

    [Fact]
    public async Task SyncEntityCerts_SbaA6_MapsTo8a()
    {
        SeedOrganization();
        SeedEntity("UEI000000001");
        SeedSbaCert("UEI000000001", "A6", exitDate: null);
        SeedLink(1, "UEI000000001", "SELF");

        await _service.SyncEntityCertsAsync(1);

        var certs = GetCerts(1);
        certs.Should().Contain(c => c.CertificationType == "8(a)");
    }

    [Fact]
    public async Task SyncEntityCerts_SbaXX_MapsToHUBZone()
    {
        SeedOrganization();
        SeedEntity("UEI000000001");
        SeedSbaCert("UEI000000001", "XX", exitDate: null);
        SeedLink(1, "UEI000000001", "SELF");

        await _service.SyncEntityCertsAsync(1);

        var certs = GetCerts(1);
        certs.Should().Contain(c => c.CertificationType == "HUBZone");
    }

    // =======================================================================
    // SyncEntityCertsAsync — SDB rule
    // =======================================================================

    [Fact]
    public async Task SyncEntityCerts_AnyCertFound_AlsoAddsSDB()
    {
        SeedOrganization();
        SeedEntity("UEI000000001");
        SeedBusinessType("UEI000000001", "8W");
        SeedLink(1, "UEI000000001", "SELF");

        await _service.SyncEntityCertsAsync(1);

        var certs = GetCerts(1);
        certs.Should().Contain(c => c.CertificationType == "SDB",
            "any small-business cert should also add SDB");
    }

    [Fact]
    public async Task SyncEntityCerts_NoCertsFound_NoSDB()
    {
        SeedOrganization();
        SeedEntity("UEI000000001");
        // Entity with no relevant business types or SBA certs
        SeedBusinessType("UEI000000001", "ZZ"); // not a mapped code
        SeedLink(1, "UEI000000001", "SELF");

        await _service.SyncEntityCertsAsync(1);

        var certs = GetCerts(1);
        certs.Should().BeEmpty("unmapped business type should not produce any certs");
    }

    // =======================================================================
    // SyncEntityCertsAsync — Multi-entity aggregation
    // =======================================================================

    [Fact]
    public async Task SyncEntityCerts_MultipleEntities_AggregatesCerts()
    {
        SeedOrganization();

        SeedEntity("UEI_SELF_001", "Self Corp");
        SeedBusinessType("UEI_SELF_001", "8W"); // WOSB

        SeedEntity("UEI_JV_00001", "JV Partner Inc");
        SeedSbaCert("UEI_JV_00001", "A4", exitDate: null); // 8(a)

        SeedLink(1, "UEI_SELF_001", "SELF");
        SeedLink(1, "UEI_JV_00001", "JV_PARTNER");

        await _service.SyncEntityCertsAsync(1);

        var certs = GetCerts(1);
        certs.Should().Contain(c => c.CertificationType == "WOSB", "from SELF entity");
        certs.Should().Contain(c => c.CertificationType == "8(a)", "from JV entity");
        certs.Should().Contain(c => c.CertificationType == "SDB", "general rule");
    }

    [Fact]
    public async Task SyncEntityCerts_DuplicateAcrossEntities_Deduplicates()
    {
        SeedOrganization();

        SeedEntity("UEI_SELF_001", "Self Corp");
        SeedBusinessType("UEI_SELF_001", "8W"); // WOSB

        SeedEntity("UEI_JV_00001", "JV Partner Inc");
        SeedBusinessType("UEI_JV_00001", "8W"); // also WOSB

        SeedLink(1, "UEI_SELF_001", "SELF");
        SeedLink(1, "UEI_JV_00001", "JV_PARTNER");

        await _service.SyncEntityCertsAsync(1);

        var certs = GetCerts(1);
        certs.Count(c => c.CertificationType == "WOSB").Should().Be(1,
            "WOSB from SELF and JV should be deduplicated to one row");
    }

    // =======================================================================
    // SyncEntityCertsAsync — No linked entities
    // =======================================================================

    [Fact]
    public async Task SyncEntityCerts_NoLinkedEntities_RemovesAllSamEntityRows()
    {
        SeedOrganization();
        // Pre-populate with SAM_ENTITY certs
        SeedSamEntityCert(1, "WOSB");
        SeedSamEntityCert(1, "SDB");

        // No active links exist
        var result = await _service.SyncEntityCertsAsync(1);

        result.Should().Be(0);
        var certs = GetCerts(1);
        certs.Should().BeEmpty();
    }

    [Fact]
    public async Task SyncEntityCerts_NoLinkedEntities_PreservesManualRows()
    {
        SeedOrganization();
        SeedManualCert(1, "ISO 9001");
        SeedSamEntityCert(1, "WOSB");

        // No active links
        await _service.SyncEntityCertsAsync(1);

        var certs = GetCerts(1);
        certs.Should().HaveCount(1);
        certs[0].CertificationType.Should().Be("ISO 9001");
        certs[0].Source.Should().Be("MANUAL");
    }

    // =======================================================================
    // SyncEntityCertsAsync — SAM_ENTITY vs MANUAL source preservation
    // =======================================================================

    [Fact]
    public async Task SyncEntityCerts_DeletesSamEntityRows_PreservesManualRows()
    {
        SeedOrganization();
        SeedManualCert(1, "CMMI");
        SeedManualCert(1, "FedRAMP");

        SeedEntity("UEI000000001");
        SeedBusinessType("UEI000000001", "8W");
        SeedLink(1, "UEI000000001", "SELF");

        await _service.SyncEntityCertsAsync(1);

        var certs = GetCerts(1);
        certs.Should().Contain(c => c.Source == "MANUAL" && c.CertificationType == "CMMI");
        certs.Should().Contain(c => c.Source == "MANUAL" && c.CertificationType == "FedRAMP");
        certs.Should().Contain(c => c.Source == "SAM_ENTITY" && c.CertificationType == "WOSB");
        certs.Should().Contain(c => c.Source == "SAM_ENTITY" && c.CertificationType == "SDB");
    }

    [Fact]
    public async Task SyncEntityCerts_AllSamEntityCertsHaveCorrectSource()
    {
        SeedOrganization();
        SeedEntity("UEI000000001");
        SeedBusinessType("UEI000000001", "8W");
        SeedBusinessType("UEI000000001", "QF");
        SeedLink(1, "UEI000000001", "SELF");

        await _service.SyncEntityCertsAsync(1);

        var samCerts = _context.OrganizationCertifications
            .Where(c => c.OrganizationId == 1 && c.Source == "SAM_ENTITY")
            .ToList();
        samCerts.Should().AllSatisfy(c =>
        {
            c.CertifyingAgency.Should().Be("SAM.gov");
            c.IsActive.Should().Be("Y");
        });
    }

    [Fact]
    public async Task SyncEntityCerts_ReturnsCountOfSyncedCerts()
    {
        SeedOrganization();
        SeedEntity("UEI000000001");
        SeedBusinessType("UEI000000001", "8W"); // WOSB
        SeedBusinessType("UEI000000001", "QF"); // SDVOSB
        SeedLink(1, "UEI000000001", "SELF");

        var result = await _service.SyncEntityCertsAsync(1);

        // WOSB + SDVOSB + SDB = 3
        result.Should().Be(3);
    }

    // =======================================================================
    // SetCertificationsAsync (CompanyProfileService) — source guard
    // =======================================================================

    [Fact]
    public async Task SetCertifications_OnlyDeletesManualRows_PreservesSamEntity()
    {
        SeedOrganization();
        SeedSamEntityCert(1, "WOSB");
        SeedSamEntityCert(1, "SDB");
        SeedManualCert(1, "ISO 9001");

        var profileService = new CompanyProfileService(_context, NullLogger<CompanyProfileService>.Instance);

        var newCerts = new List<OrgCertificationDto>
        {
            new() { CertificationType = "FedRAMP", IsActive = true }
        };
        await profileService.SetCertificationsAsync(1, newCerts);

        var allCerts = GetCerts(1);
        // SAM_ENTITY rows should remain
        allCerts.Should().Contain(c => c.Source == "SAM_ENTITY" && c.CertificationType == "WOSB");
        allCerts.Should().Contain(c => c.Source == "SAM_ENTITY" && c.CertificationType == "SDB");
        // Old MANUAL (ISO 9001) should be gone, replaced by FedRAMP
        allCerts.Should().NotContain(c => c.CertificationType == "ISO 9001");
        allCerts.Should().Contain(c => c.Source == "MANUAL" && c.CertificationType == "FedRAMP");
    }

    [Fact]
    public async Task SetCertifications_NewCertsGetSourceManual()
    {
        SeedOrganization();

        var profileService = new CompanyProfileService(_context, NullLogger<CompanyProfileService>.Instance);

        var newCerts = new List<OrgCertificationDto>
        {
            new() { CertificationType = "CMMI", IsActive = true },
            new() { CertificationType = "ISO 27001", IsActive = true }
        };
        var result = await profileService.SetCertificationsAsync(1, newCerts);

        result.Should().AllSatisfy(c => c.Source.Should().Be("MANUAL"));
    }

    // =======================================================================
    // LinkEntityAsync — triggers cert sync
    // =======================================================================

    [Fact]
    public async Task LinkEntity_SelfRelationship_TriggersCertSync()
    {
        SeedOrganization();
        var user = SeedUser();
        SeedEntity("UEI000000001");
        SeedBusinessType("UEI000000001", "8W");

        await _service.LinkEntityAsync(1, user.UserId, new LinkEntityRequest
        {
            UeiSam = "UEI000000001",
            Relationship = "SELF"
        });

        var certs = GetCerts(1);
        certs.Should().Contain(c => c.CertificationType == "WOSB",
            "linking SELF should trigger cert sync");
    }

    [Fact]
    public async Task LinkEntity_JvPartner_TriggersCertSync()
    {
        SeedOrganization();
        var user = SeedUser();
        SeedEntity("UEI000000001");
        SeedBusinessType("UEI000000001", "QF");

        await _service.LinkEntityAsync(1, user.UserId, new LinkEntityRequest
        {
            UeiSam = "UEI000000001",
            Relationship = "JV_PARTNER"
        });

        var certs = GetCerts(1);
        certs.Should().Contain(c => c.CertificationType == "SDVOSB",
            "linking JV_PARTNER should trigger cert sync");
    }

    [Fact]
    public async Task LinkEntity_Teaming_TriggersCertSync()
    {
        SeedOrganization();
        var user = SeedUser();
        SeedEntity("UEI000000001");
        SeedSbaCert("UEI000000001", "XX", exitDate: null);

        await _service.LinkEntityAsync(1, user.UserId, new LinkEntityRequest
        {
            UeiSam = "UEI000000001",
            Relationship = "TEAMING"
        });

        var certs = GetCerts(1);
        certs.Should().Contain(c => c.CertificationType == "HUBZone",
            "linking TEAMING should trigger cert sync");
    }

    // =======================================================================
    // DeactivateLinkAsync — triggers cert sync
    // =======================================================================

    [Fact]
    public async Task DeactivateLink_TriggersCertResync()
    {
        SeedOrganization();
        SeedEntity("UEI_SELF_001", "Self Corp");
        SeedBusinessType("UEI_SELF_001", "8W"); // WOSB

        SeedEntity("UEI_JV_00001", "JV Corp");
        SeedBusinessType("UEI_JV_00001", "QF"); // SDVOSB

        var selfLink = SeedLink(1, "UEI_SELF_001", "SELF");
        var jvLink = SeedLink(1, "UEI_JV_00001", "JV_PARTNER");

        // Initial sync to populate certs
        await _service.SyncEntityCertsAsync(1);
        GetCerts(1).Should().Contain(c => c.CertificationType == "SDVOSB");

        // Deactivate the JV partner
        await _service.DeactivateLinkAsync(1, jvLink.Id);

        var certs = GetCerts(1);
        certs.Should().Contain(c => c.CertificationType == "WOSB", "SELF certs should remain");
        certs.Should().NotContain(c => c.CertificationType == "SDVOSB",
            "JV partner's SDVOSB should be removed after delink");
    }

    [Fact]
    public async Task DeactivateLink_Self_ClearsUeiSam()
    {
        var org = SeedOrganization();
        SeedEntity("UEI000000001");
        var selfLink = SeedLink(1, "UEI000000001", "SELF");

        // Set UeiSam on org
        org.UeiSam = "UEI000000001";
        _context.SaveChanges();

        await _service.DeactivateLinkAsync(1, selfLink.Id);

        var updatedOrg = await _context.Organizations.FindAsync(1);
        updatedOrg!.UeiSam.Should().BeNull("delinking SELF should clear UeiSam");
    }

    [Fact]
    public async Task DeactivateLink_NonSelf_DoesNotClearUeiSam()
    {
        var org = SeedOrganization();
        org.UeiSam = "UEI_SELF_001";
        _context.SaveChanges();

        SeedEntity("UEI_SELF_001");
        SeedEntity("UEI_JV_00001");
        SeedLink(1, "UEI_SELF_001", "SELF");
        var jvLink = SeedLink(1, "UEI_JV_00001", "JV_PARTNER");

        await _service.DeactivateLinkAsync(1, jvLink.Id);

        var updatedOrg = await _context.Organizations.FindAsync(1);
        updatedOrg!.UeiSam.Should().Be("UEI_SELF_001",
            "delinking JV_PARTNER should not clear UeiSam");
    }

    // =======================================================================
    // CertificationCount — includes both SBA certs and business type codes
    // =======================================================================

    [Fact]
    public async Task GetLinkedEntities_CertificationCount_IncludesBothSbaAndBusinessTypes()
    {
        SeedOrganization();
        var entity = SeedEntity("UEI000000001");
        SeedBusinessType("UEI000000001", "8W"); // relevant
        SeedBusinessType("UEI000000001", "QF"); // relevant
        SeedBusinessType("UEI000000001", "ZZ"); // not relevant
        SeedSbaCert("UEI000000001", "A4", exitDate: null); // active SBA
        SeedLink(1, "UEI000000001", "SELF");

        var result = await _service.GetLinkedEntitiesAsync(1);

        result.Should().HaveCount(1);
        // 2 relevant business types + 1 active SBA cert = 3
        result[0].CertificationCount.Should().Be(3);
    }

    [Fact]
    public async Task GetLinkedEntities_CertificationCount_ExcludesExpiredSbaCerts()
    {
        SeedOrganization();
        SeedEntity("UEI000000001");
        SeedBusinessType("UEI000000001", "8W");
        var pastDate = DateOnly.FromDateTime(DateTime.UtcNow.AddDays(-30));
        SeedSbaCert("UEI000000001", "A4", exitDate: pastDate); // expired
        SeedLink(1, "UEI000000001", "SELF");

        var result = await _service.GetLinkedEntitiesAsync(1);

        result.Should().HaveCount(1);
        // 1 relevant business type + 0 expired SBA certs = 1
        result[0].CertificationCount.Should().Be(1);
    }

    // =======================================================================
    // SyncEntityCertsAsync — Idempotency (re-sync replaces, not appends)
    // =======================================================================

    [Fact]
    public async Task SyncEntityCerts_CalledTwice_DoesNotDuplicateCerts()
    {
        SeedOrganization();
        SeedEntity("UEI000000001");
        SeedBusinessType("UEI000000001", "8W");
        SeedLink(1, "UEI000000001", "SELF");

        await _service.SyncEntityCertsAsync(1);
        await _service.SyncEntityCertsAsync(1);

        var certs = GetCerts(1);
        certs.Count(c => c.CertificationType == "WOSB").Should().Be(1,
            "re-syncing should replace, not append");
    }

    // =======================================================================
    // SyncEntityCertsAsync — Inactive links are ignored
    // =======================================================================

    [Fact]
    public async Task SyncEntityCerts_InactiveLink_IsIgnored()
    {
        SeedOrganization();
        SeedEntity("UEI000000001");
        SeedBusinessType("UEI000000001", "8W");
        SeedLink(1, "UEI000000001", "SELF", active: false);

        await _service.SyncEntityCertsAsync(1);

        var certs = GetCerts(1);
        certs.Where(c => c.Source == "SAM_ENTITY").Should().BeEmpty(
            "inactive link should not produce any certs");
    }

    // =======================================================================
    // SyncEntityCertsAsync — Complete scenario with all cert types
    // =======================================================================

    [Fact]
    public async Task SyncEntityCerts_AllCertTypes_ProducesCorrectSet()
    {
        SeedOrganization();
        SeedEntity("UEI000000001");
        SeedBusinessType("UEI000000001", "8W");  // WOSB
        SeedBusinessType("UEI000000001", "8E");  // EDWOSB
        SeedBusinessType("UEI000000001", "QF");  // SDVOSB
        SeedBusinessType("UEI000000001", "A5");  // VOSB
        SeedSbaCert("UEI000000001", "A4", exitDate: null); // 8(a)
        SeedSbaCert("UEI000000001", "XX", exitDate: null); // HUBZone
        SeedLink(1, "UEI000000001", "SELF");

        var count = await _service.SyncEntityCertsAsync(1);

        var certs = GetCerts(1);
        var certTypes = certs.Select(c => c.CertificationType).ToHashSet();

        certTypes.Should().BeEquivalentTo(new[] { "8(a)", "EDWOSB", "HUBZone", "SDB", "SDVOSB", "VOSB", "WOSB" });
        count.Should().Be(7);
    }

    // =======================================================================
    // LinkEntityAsync — reactivation triggers cert sync
    // =======================================================================

    [Fact]
    public async Task LinkEntity_ReactivatesSelfLink_TriggersCertSync()
    {
        SeedOrganization();
        var user = SeedUser();
        SeedEntity("UEI000000001");
        SeedBusinessType("UEI000000001", "8W");

        // Create an inactive SELF link
        SeedLink(1, "UEI000000001", "SELF", active: false);

        // Reactivate by linking again
        await _service.LinkEntityAsync(1, user.UserId, new LinkEntityRequest
        {
            UeiSam = "UEI000000001",
            Relationship = "SELF"
        });

        var certs = GetCerts(1);
        certs.Should().Contain(c => c.CertificationType == "WOSB",
            "reactivating a link should trigger cert sync");
    }

    [Fact]
    public async Task LinkEntity_ReactivatesNonSelfLink_TriggersCertSync()
    {
        SeedOrganization();
        var user = SeedUser();
        SeedEntity("UEI000000001");
        SeedSbaCert("UEI000000001", "XX", exitDate: null);

        // Create an inactive JV link
        SeedLink(1, "UEI000000001", "JV_PARTNER", active: false);

        // Reactivate by linking again
        await _service.LinkEntityAsync(1, user.UserId, new LinkEntityRequest
        {
            UeiSam = "UEI000000001",
            Relationship = "JV_PARTNER"
        });

        var certs = GetCerts(1);
        certs.Should().Contain(c => c.CertificationType == "HUBZone",
            "reactivating a non-SELF link should trigger cert sync");
    }
}
