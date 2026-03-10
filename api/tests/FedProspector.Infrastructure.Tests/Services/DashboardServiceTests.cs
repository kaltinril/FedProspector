using FedProspector.Core.Models;
using FedProspector.Infrastructure.Data;
using FedProspector.Infrastructure.Services;
using FluentAssertions;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging.Abstractions;

namespace FedProspector.Infrastructure.Tests.Services;

public class DashboardServiceTests : IDisposable
{
    private readonly FedProspectorDbContext _context;
    private readonly DashboardService _service;

    public DashboardServiceTests()
    {
        var options = new DbContextOptionsBuilder<FedProspectorDbContext>()
            .UseInMemoryDatabase(databaseName: Guid.NewGuid().ToString())
            .Options;

        _context = new FedProspectorDbContext(options);
        _service = new DashboardService(_context, NullLogger<DashboardService>.Instance);
    }

    public void Dispose()
    {
        _context.Dispose();
    }

    private void SeedOrganization(int orgId = 1)
    {
        _context.Organizations.Add(new Organization
        {
            OrganizationId = orgId,
            Name = $"Org {orgId}",
            Slug = $"org-{orgId}",
            IsActive = "Y",
            MaxUsers = 10,
            CreatedAt = DateTime.UtcNow,
            UpdatedAt = DateTime.UtcNow
        });
        _context.SaveChanges();
    }

    private void SeedProspect(int orgId, string noticeId, string status,
        decimal? estimatedValue = null, string? outcome = null, int? assignedTo = null)
    {
        _context.Prospects.Add(new Prospect
        {
            OrganizationId = orgId,
            NoticeId = noticeId,
            Status = status,
            EstimatedValue = estimatedValue,
            Outcome = outcome,
            AssignedTo = assignedTo,
            CreatedAt = DateTime.UtcNow
        });

        // Ensure opportunity exists for joins
        if (!_context.Opportunities.Any(o => o.NoticeId == noticeId))
        {
            _context.Opportunities.Add(new Opportunity
            {
                NoticeId = noticeId,
                Title = $"Opportunity {noticeId}"
            });
        }

        _context.SaveChanges();
    }

    private AppUser SeedUser(int orgId, string username, string displayName)
    {
        var user = new AppUser
        {
            OrganizationId = orgId,
            Username = username,
            DisplayName = displayName,
            Email = $"{username}@example.com",
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

    // --- GetDashboardAsync tests ---

    [Fact]
    public async Task GetDashboardAsync_ReturnsMetrics()
    {
        SeedOrganization(1);
        SeedProspect(1, "NOTICE-001", "NEW", 100_000m);
        SeedProspect(1, "NOTICE-002", "REVIEWING", 200_000m);
        SeedProspect(1, "NOTICE-003", "WON", outcome: "WON");

        var result = await _service.GetDashboardAsync(1);

        result.Should().NotBeNull();
        result.ProspectsByStatus.Should().NotBeEmpty();
        result.TotalOpenProspects.Should().Be(2); // NEW + REVIEWING, WON is terminal
        result.PipelineValue.Should().Be(300_000m);
    }

    [Fact]
    public async Task GetDashboardAsync_FiltersByOrg()
    {
        SeedOrganization(1);
        SeedOrganization(2);
        SeedProspect(1, "NOTICE-001", "NEW", 100_000m);
        SeedProspect(2, "NOTICE-002", "NEW", 500_000m);

        var result1 = await _service.GetDashboardAsync(1);
        var result2 = await _service.GetDashboardAsync(2);

        result1.TotalOpenProspects.Should().Be(1);
        result1.PipelineValue.Should().Be(100_000m);
        result2.TotalOpenProspects.Should().Be(1);
        result2.PipelineValue.Should().Be(500_000m);
    }

    [Fact]
    public async Task GetDashboardAsync_EmptyData_ReturnsZeros()
    {
        SeedOrganization(1);

        var result = await _service.GetDashboardAsync(1);

        result.TotalOpenProspects.Should().Be(0);
        result.PipelineValue.Should().Be(0);
        result.ProspectsByStatus.Should().BeEmpty();
        result.DueThisWeek.Should().BeEmpty();
        result.WorkloadByAssignee.Should().BeEmpty();
        result.WinLossMetrics.Should().BeEmpty();
    }
}
