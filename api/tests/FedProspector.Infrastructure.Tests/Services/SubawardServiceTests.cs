using FedProspector.Core.DTOs.Subawards;
using FedProspector.Infrastructure.Data;
using FedProspector.Infrastructure.Services;
using FluentAssertions;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging.Abstractions;

namespace FedProspector.Infrastructure.Tests.Services;

/// <summary>
/// SubawardService uses raw SQL (MySqlConnector) which cannot run against
/// the EF Core in-memory provider. These tests verify constructor setup and
/// request validation paths only. Full integration tests require a real MySQL database.
/// </summary>
public class SubawardServiceTests : IDisposable
{
    private readonly FedProspectorDbContext _context;
    private readonly SubawardService _service;

    public SubawardServiceTests()
    {
        var options = new DbContextOptionsBuilder<FedProspectorDbContext>()
            .UseInMemoryDatabase(databaseName: Guid.NewGuid().ToString())
            .Options;

        _context = new FedProspectorDbContext(options);
        _service = new SubawardService(_context, NullLogger<SubawardService>.Instance);
    }

    public void Dispose()
    {
        _context.Dispose();
    }

    [Fact]
    public void GetTeamingPartnersAsync_ServiceCanBeConstructed()
    {
        // SubawardService uses raw ADO.NET (MySqlConnector) with GROUP BY and
        // GROUP_CONCAT which are not supported by the in-memory provider.
        // This test verifies the service can be instantiated correctly.
        _service.Should().NotBeNull();
    }

    [Fact]
    public async Task GetTeamingPartnersAsync_WithInMemoryProvider_ThrowsBecauseRawSql()
    {
        // Demonstrates that this service requires a real MySQL connection
        var request = new TeamingPartnerSearchRequest
        {
            Page = 1,
            PageSize = 10,
            MinSubawards = 2
        };

        // The in-memory provider does not support GetDbConnection() for raw SQL
        var act = () => _service.GetTeamingPartnersAsync(request);
        await act.Should().ThrowAsync<Exception>();
    }

    [Fact]
    public void GetTeamingPartnersAsync_RequestDefaults_AreCorrect()
    {
        var request = new TeamingPartnerSearchRequest();

        request.MinSubawards.Should().Be(2);
        request.Page.Should().Be(1);
        request.PageSize.Should().Be(25);
        request.Naics.Should().BeNull();
        request.PrimeUei.Should().BeNull();
        request.SubUei.Should().BeNull();
    }
}
