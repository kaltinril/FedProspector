using FedProspector.Core.Models;
using FedProspector.Infrastructure.Data;
using FedProspector.Infrastructure.Services;
using FluentAssertions;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging.Abstractions;

namespace FedProspector.Infrastructure.Tests.Services;

public class ActivityLogServiceTests : IDisposable
{
    private readonly FedProspectorDbContext _context;
    private readonly ActivityLogService _service;

    public ActivityLogServiceTests()
    {
        var options = new DbContextOptionsBuilder<FedProspectorDbContext>()
            .UseInMemoryDatabase(databaseName: Guid.NewGuid().ToString())
            .Options;

        _context = new FedProspectorDbContext(options);
        _service = new ActivityLogService(_context, NullLogger<ActivityLogService>.Instance);
    }

    public void Dispose()
    {
        _context.Dispose();
    }

    // --- LogAsync (without orgId) tests ---

    [Fact]
    public async Task LogAsync_ValidInput_CreatesLogEntry()
    {
        await _service.LogAsync(
            userId: 1,
            action: "LOGIN",
            entityType: "USER",
            entityId: "1",
            details: new { Source = "web" },
            ipAddress: "192.168.1.1");

        var entry = await _context.ActivityLogs.FirstOrDefaultAsync();
        entry.Should().NotBeNull();
        entry!.UserId.Should().Be(1);
        entry.Action.Should().Be("LOGIN");
        entry.EntityType.Should().Be("USER");
        entry.EntityId.Should().Be("1");
        entry.OrganizationId.Should().Be(1); // default org for legacy calls
        entry.IpAddress.Should().Be("192.168.1.1");
        entry.Details.Should().Contain("Source");
        entry.CreatedAt.Should().NotBeNull();
    }

    // --- LogAsync (with orgId) tests ---

    [Fact]
    public async Task LogAsync_WithOrgId_CreatesLogEntry()
    {
        await _service.LogAsync(
            organizationId: 42,
            userId: 5,
            action: "CREATE_PROSPECT",
            entityType: "PROSPECT",
            entityId: "100");

        var entry = await _context.ActivityLogs.FirstOrDefaultAsync();
        entry.Should().NotBeNull();
        entry!.OrganizationId.Should().Be(42);
        entry.UserId.Should().Be(5);
        entry.Action.Should().Be("CREATE_PROSPECT");
        entry.EntityType.Should().Be("PROSPECT");
        entry.EntityId.Should().Be("100");
    }

    // --- Null userId tests ---

    [Fact]
    public async Task LogAsync_NullUserId_StillCreates()
    {
        await _service.LogAsync(
            userId: null,
            action: "SYSTEM_CLEANUP",
            entityType: "SYSTEM",
            entityId: null);

        var entry = await _context.ActivityLogs.FirstOrDefaultAsync();
        entry.Should().NotBeNull();
        entry!.UserId.Should().BeNull();
        entry.Action.Should().Be("SYSTEM_CLEANUP");
        entry.EntityId.Should().BeNull();
    }
}
