using FedProspector.Core.DTOs.Admin;
using FedProspector.Core.Interfaces;
using FedProspector.Core.Models;
using FedProspector.Infrastructure.Data;
using FedProspector.Infrastructure.Services;
using FluentAssertions;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging.Abstractions;
using Moq;

namespace FedProspector.Infrastructure.Tests.Services;

public class AdminServiceTests : IDisposable
{
    private readonly FedProspectorDbContext _context;
    private readonly AdminService _service;
    private readonly Mock<IAuthService> _authServiceMock;
    private readonly Mock<IActivityLogService> _activityLogServiceMock;

    public AdminServiceTests()
    {
        var options = new DbContextOptionsBuilder<FedProspectorDbContext>()
            .UseInMemoryDatabase(databaseName: Guid.NewGuid().ToString())
            .Options;

        _context = new FedProspectorDbContext(options);
        _authServiceMock = new Mock<IAuthService>();
        _activityLogServiceMock = new Mock<IActivityLogService>();
        _service = new AdminService(
            _context,
            NullLogger<AdminService>.Instance,
            _authServiceMock.Object,
            _activityLogServiceMock.Object);
    }

    public void Dispose()
    {
        _context.Dispose();
    }

    private Organization SeedOrganization(int orgId = 1)
    {
        var org = new Organization
        {
            OrganizationId = orgId,
            Name = $"Org {orgId}",
            Slug = $"org-{orgId}",
            IsActive = "Y",
            MaxUsers = 10,
            CreatedAt = DateTime.UtcNow,
            UpdatedAt = DateTime.UtcNow
        };
        _context.Organizations.Add(org);
        _context.SaveChanges();
        return org;
    }

    private AppUser SeedUser(int orgId = 1, string username = "testuser", string email = "test@example.com",
        bool isActive = true, bool isOrgAdmin = false)
    {
        var user = new AppUser
        {
            OrganizationId = orgId,
            Username = username,
            DisplayName = username,
            Email = email,
            PasswordHash = "hash",
            Role = "USER",
            OrgRole = "member",
            IsActive = isActive ? "Y" : "N",
            IsOrgAdmin = isOrgAdmin ? "Y" : "N",
            MfaEnabled = "N",
            ForcePasswordChange = "N",
            FailedLoginAttempts = 0,
            CreatedAt = DateTime.UtcNow
        };
        _context.AppUsers.Add(user);
        _context.SaveChanges();
        return user;
    }

    // --- GetEtlStatusAsync tests ---

    [Fact]
    public async Task GetEtlStatusAsync_ReturnsStatus()
    {
        // Seed a successful load log
        _context.EtlLoadLogs.Add(new EtlLoadLog
        {
            SourceSystem = "SAM_OPPORTUNITY",
            LoadType = "INCREMENTAL",
            Status = "SUCCESS",
            StartedAt = DateTime.Now.AddHours(-2),
            CompletedAt = DateTime.Now.AddHours(-1),
            RecordsRead = 100,
            RecordsInserted = 50,
            RecordsUpdated = 30,
            RecordsUnchanged = 20,
            RecordsErrored = 0
        });
        _context.SaveChanges();

        var result = await _service.GetEtlStatusAsync();

        result.Should().NotBeNull();
        result.Sources.Should().NotBeEmpty();
        result.Alerts.Should().NotBeEmpty();

        // The SAM_OPPORTUNITY source should have data
        var oppSource = result.Sources.FirstOrDefault(s => s.SourceSystem == "SAM_OPPORTUNITY");
        oppSource.Should().NotBeNull();
        oppSource!.LastLoadAt.Should().NotBeNull();
        oppSource.RecordsProcessed.Should().Be(80); // 50 inserted + 30 updated
    }

    // --- GetUsersAsync tests ---

    [Fact]
    public async Task GetUsersAsync_PaginatesCorrectly()
    {
        SeedOrganization(1);
        for (int i = 1; i <= 5; i++)
            SeedUser(1, $"user{i}", $"user{i}@example.com");

        var result = await _service.GetUsersAsync(1, page: 1, pageSize: 2);

        result.TotalCount.Should().Be(5);
        result.Items.Should().HaveCount(2);
        result.Page.Should().Be(1);
        result.PageSize.Should().Be(2);
    }

    [Fact]
    public async Task GetUsersAsync_FiltersByOrg()
    {
        SeedOrganization(1);
        SeedOrganization(2);
        SeedUser(1, "org1user", "org1@example.com");
        SeedUser(2, "org2user", "org2@example.com");

        var result1 = await _service.GetUsersAsync(1);
        var result2 = await _service.GetUsersAsync(2);

        result1.TotalCount.Should().Be(1);
        result1.Items.First().Username.Should().Be("org1user");
        result2.TotalCount.Should().Be(1);
        result2.Items.First().Username.Should().Be("org2user");
    }

    // --- UpdateUserAsync tests ---

    [Fact]
    public async Task UpdateUserAsync_ValidRequest_UpdatesUser()
    {
        SeedOrganization(1);
        var admin = SeedUser(1, "admin", "admin@example.com", isOrgAdmin: true);
        var target = SeedUser(1, "target", "target@example.com");

        var request = new UpdateUserRequest { Role = "MANAGER", IsOrgAdmin = true };

        var result = await _service.UpdateUserAsync(target.UserId, request, admin.UserId, 1);

        result.Role.Should().Be("MANAGER");
        result.IsOrgAdmin.Should().BeTrue();

        _activityLogServiceMock.Verify(
            a => a.LogAsync(admin.UserId, "ADMIN_UPDATE_USER", "USER", target.UserId.ToString(), It.IsAny<object>(), null),
            Times.Once);
    }

    // --- ResetPasswordAsync tests ---

    [Fact]
    public async Task ResetPasswordAsync_ValidUser_ReturnsNewPassword()
    {
        SeedOrganization(1);
        var admin = SeedUser(1, "admin", "admin@example.com", isOrgAdmin: true);
        var target = SeedUser(1, "target", "target@example.com");

        _authServiceMock.Setup(a => a.HashPassword(It.IsAny<string>())).Returns("newhash");

        var result = await _service.ResetPasswordAsync(target.UserId, admin.UserId, 1);

        result.Should().NotBeNull();
        result.Message.Should().Contain("target");
        result.TemporaryPassword.Should().NotBeNullOrEmpty();
        result.TemporaryPassword.Length.Should().Be(12);

        // Verify user was updated
        var user = await _context.AppUsers.FindAsync(target.UserId);
        user!.PasswordHash.Should().Be("newhash");
        user.ForcePasswordChange.Should().Be("Y");

        _activityLogServiceMock.Verify(
            a => a.LogAsync(admin.UserId, "ADMIN_RESET_PASSWORD", "USER", target.UserId.ToString(), It.IsAny<object>(), null),
            Times.Once);
    }
}
