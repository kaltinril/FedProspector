using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using FedProspector.Api.Controllers;
using FedProspector.Core.DTOs.Dashboard;
using FedProspector.Core.Interfaces;
using FluentAssertions;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Moq;

namespace FedProspector.Api.Tests.Controllers;

public class DashboardControllerTests
{
    private readonly Mock<IDashboardService> _serviceMock = new();
    private readonly DashboardController _controller;

    public DashboardControllerTests()
    {
        _controller = new DashboardController(_serviceMock.Object);
        _controller.ControllerContext = new ControllerContext
        {
            HttpContext = new DefaultHttpContext()
        };
    }

    private static ClaimsPrincipal CreateUser(int userId = 1, int orgId = 1)
    {
        var claims = new List<Claim>
        {
            new(JwtRegisteredClaimNames.Sub, userId.ToString()),
            new(ClaimTypes.NameIdentifier, userId.ToString()),
            new("org_id", orgId.ToString())
        };
        return new ClaimsPrincipal(new ClaimsIdentity(claims, "TestAuth"));
    }

    private void SetAuthenticatedUser(int userId = 1, int orgId = 1)
    {
        _controller.ControllerContext.HttpContext.User = CreateUser(userId, orgId);
    }

    [Fact]
    public async Task GetDashboard_NoUser_ReturnsUnauthorized()
    {
        var result = await _controller.GetDashboard();

        result.Should().BeOfType<UnauthorizedResult>();
    }

    [Fact]
    public async Task GetDashboard_ReturnsOk()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        _serviceMock.Setup(s => s.GetDashboardAsync(10))
            .ReturnsAsync(new DashboardDto());

        var result = await _controller.GetDashboard();

        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task GetDashboard_CallsService()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        _serviceMock.Setup(s => s.GetDashboardAsync(10))
            .ReturnsAsync(new DashboardDto());

        await _controller.GetDashboard();

        _serviceMock.Verify(s => s.GetDashboardAsync(10), Times.Once);
    }

    [Fact]
    public async Task GetDashboard_ReturnsServiceResult()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        var expected = new DashboardDto { TotalOpenProspects = 10 };
        _serviceMock.Setup(s => s.GetDashboardAsync(10)).ReturnsAsync(expected);

        var result = await _controller.GetDashboard() as OkObjectResult;

        result!.Value.Should().Be(expected);
    }
}
