using FedProspector.Api.Controllers;
using FedProspector.Core.DTOs.Health;
using FedProspector.Infrastructure.Data;
using FluentAssertions;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using Moq;

namespace FedProspector.Api.Tests.Controllers;

/// <summary>
/// HealthController uses FedProspectorDbContext directly (not a service interface).
/// Because it calls Database.ExecuteSqlRawAsync and Database.SqlQueryRaw which are
/// extremely difficult to mock with EF Core, we test the response model structure
/// and verify the controller type/route attributes instead.
/// </summary>
public class HealthControllerTests
{
    [Fact]
    public void HealthController_HasRouteAttribute()
    {
        var attrs = typeof(HealthController).GetCustomAttributes(typeof(RouteAttribute), true);
        attrs.Should().ContainSingle();
        ((RouteAttribute)attrs[0]).Template.Should().Be("health");
    }

    [Fact]
    public void HealthController_InheritsControllerBase()
    {
        typeof(HealthController).BaseType.Should().Be(typeof(ControllerBase));
    }

    [Fact]
    public void HealthResponse_DefaultStatus_IsHealthy()
    {
        var response = new HealthResponse();
        response.Status.Should().Be("healthy");
    }

    [Fact]
    public void HealthResponse_DefaultDatabase_IsUnknown()
    {
        var response = new HealthResponse();
        response.Database.Should().Be("unknown");
    }
}
