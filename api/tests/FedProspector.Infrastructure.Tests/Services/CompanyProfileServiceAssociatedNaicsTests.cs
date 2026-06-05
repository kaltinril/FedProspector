using FedProspector.Core.DTOs.Organizations;
using FedProspector.Core.Models;
using FedProspector.Infrastructure.Data;
using FedProspector.Infrastructure.Services;
using FluentAssertions;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging.Abstractions;

namespace FedProspector.Infrastructure.Tests.Services;

/// <summary>
/// Phase 136 Unit G: associated-NAICS CRUD on <see cref="CompanyProfileService"/>
/// (manual, user-prioritized list beyond registered + linked-entity codes).
/// Harness mirrors the other Infrastructure service tests: in-memory EF Core, NullLogger,
/// FluentAssertions.
/// </summary>
public class CompanyProfileServiceAssociatedNaicsTests : IDisposable
{
    private readonly FedProspectorDbContext _context;
    private readonly CompanyProfileService _service;

    public CompanyProfileServiceAssociatedNaicsTests()
    {
        var options = new DbContextOptionsBuilder<FedProspectorDbContext>()
            .UseInMemoryDatabase(databaseName: Guid.NewGuid().ToString())
            .Options;

        _context = new FedProspectorDbContext(options);
        _service = new CompanyProfileService(_context, NullLogger<CompanyProfileService>.Instance);
    }

    public void Dispose() => _context.Dispose();

    private void SeedOrganization(int orgId = 1)
    {
        _context.Organizations.Add(new Organization
        {
            OrganizationId = orgId,
            Name = "Test Org",
            Slug = $"test-org-{orgId}",
            IsActive = "Y",
            MaxUsers = 10,
            SubscriptionTier = "trial",
            CreatedAt = DateTime.UtcNow,
            UpdatedAt = DateTime.UtcNow
        });
        _context.SaveChanges();
    }

    private void SeedRegisteredNaics(int orgId, string code)
    {
        _context.OrganizationNaics.Add(new OrganizationNaics
        {
            OrganizationId = orgId,
            NaicsCode = code,
            IsPrimary = "Y",
            SizeStandardMet = "Y",
            CreatedAt = DateTime.UtcNow
        });
        _context.SaveChanges();
    }

    [Fact]
    public async Task Add_PersistsCodeAndNote()
    {
        SeedOrganization();

        var dto = await _service.AddAssociatedNaicsAsync(1, new CreateAssociatedNaicsRequest
        {
            NaicsCode = "541512",
            Note = "Adjacent IT services"
        });

        dto.NaicsCode.Should().Be("541512");
        dto.Note.Should().Be("Adjacent IT services");

        var list = await _service.GetAssociatedNaicsAsync(1);
        list.Should().ContainSingle(n => n.NaicsCode == "541512" && n.Note == "Adjacent IT services");
    }

    [Fact]
    public async Task Add_DuplicateCode_IsIdempotent()
    {
        SeedOrganization();
        var first = await _service.AddAssociatedNaicsAsync(1, new CreateAssociatedNaicsRequest { NaicsCode = "541512" });
        var second = await _service.AddAssociatedNaicsAsync(1, new CreateAssociatedNaicsRequest { NaicsCode = "541512" });

        second.Id.Should().Be(first.Id, "re-adding the same code returns the existing row, not a duplicate");
        var list = await _service.GetAssociatedNaicsAsync(1);
        list.Should().HaveCount(1);
    }

    [Fact]
    public async Task Add_FreshCode_AlreadyExistedIsFalse()
    {
        SeedOrganization();

        var dto = await _service.AddAssociatedNaicsAsync(1, new CreateAssociatedNaicsRequest { NaicsCode = "541512" });

        dto.AlreadyExisted.Should().BeFalse("a brand-new code is a real add, not a re-add");
    }

    [Fact]
    public async Task Add_DuplicateCode_FlagsAlreadyExisted()
    {
        SeedOrganization();
        await _service.AddAssociatedNaicsAsync(1, new CreateAssociatedNaicsRequest { NaicsCode = "541512" });

        var second = await _service.AddAssociatedNaicsAsync(1, new CreateAssociatedNaicsRequest { NaicsCode = "541512" });

        second.AlreadyExisted.Should().BeTrue("the idempotent re-add must tell the caller the code was already on the list");
    }

    [Fact]
    public async Task Add_CodeAlreadyRegistered_Throws()
    {
        SeedOrganization();
        // A code the org has REGISTERED (organization_naics) must not also be added as "associated"
        // — the associated list is for codes beyond the registered ones.
        SeedRegisteredNaics(1, "541512");

        var act = async () => await _service.AddAssociatedNaicsAsync(1, new CreateAssociatedNaicsRequest { NaicsCode = "541512" });

        await act.Should().ThrowAsync<InvalidOperationException>()
            .WithMessage("*already one of your registered NAICS*");
        (await _service.GetAssociatedNaicsAsync(1)).Should().BeEmpty("the rejected code must not be persisted");
    }

    [Fact]
    public async Task Add_RegisteredCheck_IsScopedToOrg()
    {
        SeedOrganization(1);
        SeedOrganization(2);
        // Org 2 registered 541512; org 1 has not, so org 1 may still add it as associated.
        SeedRegisteredNaics(2, "541512");

        var dto = await _service.AddAssociatedNaicsAsync(1, new CreateAssociatedNaicsRequest { NaicsCode = "541512" });

        dto.NaicsCode.Should().Be("541512");
        (await _service.GetAssociatedNaicsAsync(1)).Should().ContainSingle(n => n.NaicsCode == "541512");
    }

    [Theory]
    [InlineData("54151")]    // 5 digits
    [InlineData("5415123")]  // 7 digits
    [InlineData("54151A")]   // non-digit
    [InlineData("")]
    public async Task Add_InvalidCode_Throws(string code)
    {
        SeedOrganization();

        var act = async () => await _service.AddAssociatedNaicsAsync(1, new CreateAssociatedNaicsRequest { NaicsCode = code });

        await act.Should().ThrowAsync<InvalidOperationException>();
    }

    [Fact]
    public async Task Add_TrimsCodeAndBlankNoteBecomesNull()
    {
        SeedOrganization();

        var dto = await _service.AddAssociatedNaicsAsync(1, new CreateAssociatedNaicsRequest
        {
            NaicsCode = " 541512 ",
            Note = "   "
        });

        dto.NaicsCode.Should().Be("541512");
        dto.Note.Should().BeNull();
    }

    [Fact]
    public async Task Delete_RemovesRow_AndReturnsTrue()
    {
        SeedOrganization();
        var dto = await _service.AddAssociatedNaicsAsync(1, new CreateAssociatedNaicsRequest { NaicsCode = "541512" });

        var deleted = await _service.DeleteAssociatedNaicsAsync(1, dto.Id);

        deleted.Should().BeTrue();
        (await _service.GetAssociatedNaicsAsync(1)).Should().BeEmpty();
    }

    [Fact]
    public async Task Delete_WrongOrg_ReturnsFalse()
    {
        SeedOrganization(1);
        SeedOrganization(2);
        var dto = await _service.AddAssociatedNaicsAsync(1, new CreateAssociatedNaicsRequest { NaicsCode = "541512" });

        var deleted = await _service.DeleteAssociatedNaicsAsync(2, dto.Id);

        deleted.Should().BeFalse("org 2 must not delete org 1's associated NAICS");
        (await _service.GetAssociatedNaicsAsync(1)).Should().HaveCount(1);
    }

    [Fact]
    public async Task Get_IsScopedToOrg()
    {
        SeedOrganization(1);
        SeedOrganization(2);
        await _service.AddAssociatedNaicsAsync(1, new CreateAssociatedNaicsRequest { NaicsCode = "541512" });
        await _service.AddAssociatedNaicsAsync(2, new CreateAssociatedNaicsRequest { NaicsCode = "236220" });

        var org1 = await _service.GetAssociatedNaicsAsync(1);
        org1.Should().ContainSingle(n => n.NaicsCode == "541512");
        org1.Should().NotContain(n => n.NaicsCode == "236220");
    }
}
