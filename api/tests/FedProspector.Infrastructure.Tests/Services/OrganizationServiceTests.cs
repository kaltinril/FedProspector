using FedProspector.Core.Interfaces;
using FedProspector.Core.Models;
using FedProspector.Infrastructure.Data;
using FedProspector.Infrastructure.Services;
using FluentAssertions;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging.Abstractions;
using Moq;

namespace FedProspector.Infrastructure.Tests.Services;

public class OrganizationServiceTests : IDisposable
{
    private readonly FedProspectorDbContext _context;
    private readonly OrganizationService _service;
    private readonly Mock<IAuthService> _authServiceMock;
    private readonly Mock<IActivityLogService> _activityLogServiceMock;

    public OrganizationServiceTests()
    {
        var options = new DbContextOptionsBuilder<FedProspectorDbContext>()
            .UseInMemoryDatabase(databaseName: Guid.NewGuid().ToString())
            .Options;

        _context = new FedProspectorDbContext(options);
        _authServiceMock = new Mock<IAuthService>();
        _activityLogServiceMock = new Mock<IActivityLogService>();
        _service = new OrganizationService(
            _context,
            _authServiceMock.Object,
            _activityLogServiceMock.Object,
            NullLogger<OrganizationService>.Instance);
    }

    public void Dispose()
    {
        _context.Dispose();
    }

    private Organization SeedOrganization(int orgId = 1, string name = "Test Org", string slug = "test-org", int maxUsers = 10)
    {
        var org = new Organization
        {
            OrganizationId = orgId,
            Name = name,
            Slug = slug,
            IsActive = "Y",
            MaxUsers = maxUsers,
            SubscriptionTier = "trial",
            CreatedAt = DateTime.UtcNow,
            UpdatedAt = DateTime.UtcNow
        };
        _context.Organizations.Add(org);
        _context.SaveChanges();
        return org;
    }

    private AppUser SeedUser(int orgId = 1, string username = "testuser", string email = "test@example.com",
        string orgRole = "member", string displayName = "Test User")
    {
        var user = new AppUser
        {
            OrganizationId = orgId,
            Username = username,
            DisplayName = displayName,
            Email = email,
            PasswordHash = "hash",
            Role = "USER",
            OrgRole = orgRole,
            IsActive = "Y",
            IsAdmin = "N",
            MfaEnabled = "N",
            ForcePasswordChange = "N",
            FailedLoginAttempts = 0,
            CreatedAt = DateTime.UtcNow
        };
        _context.AppUsers.Add(user);
        _context.SaveChanges();
        return user;
    }

    // --- GetOrganizationAsync tests ---

    [Fact]
    public async Task GetOrganizationAsync_ExistingOrg_ReturnsOrg()
    {
        SeedOrganization(1, "Acme Corp", "acme-corp");

        var result = await _service.GetOrganizationAsync(1);

        result.Name.Should().Be("Acme Corp");
        result.Slug.Should().Be("acme-corp");
        result.IsActive.Should().BeTrue();
    }

    [Fact]
    public async Task GetOrganizationAsync_NonexistentOrg_Throws()
    {
        var act = () => _service.GetOrganizationAsync(999);

        await act.Should().ThrowAsync<KeyNotFoundException>()
            .WithMessage("*999*");
    }

    // --- UpdateOrganizationAsync tests ---

    [Fact]
    public async Task UpdateOrganizationAsync_ValidName_Updates()
    {
        SeedOrganization(1, "Old Name");

        var result = await _service.UpdateOrganizationAsync(1, "New Name");

        result.Name.Should().Be("New Name");

        // Verify persisted
        var org = await _context.Organizations.FindAsync(1);
        org!.Name.Should().Be("New Name");
    }

    // --- GetMembersAsync tests ---

    [Fact]
    public async Task GetMembersAsync_ReturnsOrgMembers()
    {
        SeedOrganization(1);
        SeedUser(1, "alice", "alice@example.com", "owner", "Alice");
        SeedUser(1, "bob", "bob@example.com", "member", "Bob");
        SeedUser(2, "charlie", "charlie@example.com", "member", "Charlie"); // different org

        // Need org 2 to exist for FK
        SeedOrganization(2, "Other Org", "other-org");

        var result = await _service.GetMembersAsync(1);

        result.Should().HaveCount(2);
        result.Select(m => m.DisplayName).Should().BeEquivalentTo(["Alice", "Bob"]);
    }

    // --- CreateInviteAsync tests ---

    [Fact]
    public async Task CreateInviteAsync_ValidEmail_CreatesInvite()
    {
        var org = SeedOrganization(1);
        var inviter = SeedUser(1, "admin", "admin@example.com", "owner", "Admin");

        var result = await _service.CreateInviteAsync(1, "newuser@example.com", "member", inviter.UserId);

        result.Email.Should().Be("newuser@example.com");
        result.OrgRole.Should().Be("member");
        result.InvitedByName.Should().Be("Admin");
        result.ExpiresAt.Should().BeAfter(DateTime.UtcNow);

        // Verify persisted
        var invite = await _context.OrganizationInvites.FirstOrDefaultAsync();
        invite.Should().NotBeNull();
        invite!.Email.Should().Be("newuser@example.com");
    }

    [Fact]
    public async Task CreateInviteAsync_DuplicateEmail_Throws()
    {
        SeedOrganization(1);
        var inviter = SeedUser(1, "admin", "admin@example.com", "owner", "Admin");

        // Create first invite
        _context.OrganizationInvites.Add(new OrganizationInvite
        {
            OrganizationId = 1,
            Email = "dupe@example.com",
            InviteCode = "abc123",
            OrgRole = "member",
            InvitedBy = inviter.UserId,
            ExpiresAt = DateTime.UtcNow.AddDays(7),
            CreatedAt = DateTime.UtcNow
        });
        _context.SaveChanges();

        var act = () => _service.CreateInviteAsync(1, "dupe@example.com", "member", inviter.UserId);

        await act.Should().ThrowAsync<InvalidOperationException>()
            .WithMessage("*pending invite*");
    }

    // --- RevokeInviteAsync tests ---

    [Fact]
    public async Task RevokeInviteAsync_ExistingInvite_Succeeds()
    {
        SeedOrganization(1);
        var inviter = SeedUser(1, "admin", "admin@example.com", "owner", "Admin");

        var invite = new OrganizationInvite
        {
            OrganizationId = 1,
            Email = "revoke@example.com",
            InviteCode = "revoke123",
            OrgRole = "member",
            InvitedBy = inviter.UserId,
            ExpiresAt = DateTime.UtcNow.AddDays(7),
            CreatedAt = DateTime.UtcNow
        };
        _context.OrganizationInvites.Add(invite);
        _context.SaveChanges();

        await _service.RevokeInviteAsync(1, invite.InviteId);

        var remaining = await _context.OrganizationInvites.CountAsync();
        remaining.Should().Be(0);
    }

    // --- GetPendingInvitesAsync tests ---

    [Fact]
    public async Task GetPendingInvitesAsync_ReturnsPendingOnly()
    {
        SeedOrganization(1);
        var inviter = SeedUser(1, "admin", "admin@example.com", "owner", "Admin");

        // Pending invite
        _context.OrganizationInvites.Add(new OrganizationInvite
        {
            OrganizationId = 1,
            Email = "pending@example.com",
            InviteCode = "pending123",
            OrgRole = "member",
            InvitedBy = inviter.UserId,
            ExpiresAt = DateTime.UtcNow.AddDays(7),
            CreatedAt = DateTime.UtcNow
        });

        // Accepted invite
        _context.OrganizationInvites.Add(new OrganizationInvite
        {
            OrganizationId = 1,
            Email = "accepted@example.com",
            InviteCode = "accepted123",
            OrgRole = "member",
            InvitedBy = inviter.UserId,
            ExpiresAt = DateTime.UtcNow.AddDays(7),
            AcceptedAt = DateTime.UtcNow.AddDays(-1),
            CreatedAt = DateTime.UtcNow.AddDays(-2)
        });

        // Expired invite
        _context.OrganizationInvites.Add(new OrganizationInvite
        {
            OrganizationId = 1,
            Email = "expired@example.com",
            InviteCode = "expired123",
            OrgRole = "member",
            InvitedBy = inviter.UserId,
            ExpiresAt = DateTime.UtcNow.AddDays(-1),
            CreatedAt = DateTime.UtcNow.AddDays(-8)
        });

        _context.SaveChanges();

        var result = await _service.GetPendingInvitesAsync(1);

        result.Should().HaveCount(1);
        result[0].Email.Should().Be("pending@example.com");
    }
}
