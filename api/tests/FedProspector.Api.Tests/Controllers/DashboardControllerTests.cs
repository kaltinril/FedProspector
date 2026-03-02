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

    [Fact]
    public async Task GetDashboard_ReturnsOk()
    {
        _serviceMock.Setup(s => s.GetDashboardAsync())
            .ReturnsAsync(new DashboardDto());

        var result = await _controller.GetDashboard();

        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task GetDashboard_CallsService()
    {
        _serviceMock.Setup(s => s.GetDashboardAsync())
            .ReturnsAsync(new DashboardDto());

        await _controller.GetDashboard();

        _serviceMock.Verify(s => s.GetDashboardAsync(), Times.Once);
    }

    [Fact]
    public async Task GetDashboard_ReturnsServiceResult()
    {
        var expected = new DashboardDto { TotalOpenProspects = 10 };
        _serviceMock.Setup(s => s.GetDashboardAsync()).ReturnsAsync(expected);

        var result = await _controller.GetDashboard() as OkObjectResult;

        result!.Value.Should().Be(expected);
    }
}
