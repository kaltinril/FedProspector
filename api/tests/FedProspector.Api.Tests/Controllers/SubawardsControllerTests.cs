using FedProspector.Api.Controllers;
using FedProspector.Core.DTOs;
using FedProspector.Core.DTOs.Subawards;
using FedProspector.Core.Interfaces;
using FluentAssertions;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Moq;

namespace FedProspector.Api.Tests.Controllers;

public class SubawardsControllerTests
{
    private readonly Mock<ISubawardService> _serviceMock = new();
    private readonly SubawardsController _controller;

    public SubawardsControllerTests()
    {
        _controller = new SubawardsController(_serviceMock.Object);
        _controller.ControllerContext = new ControllerContext
        {
            HttpContext = new DefaultHttpContext()
        };
    }

    [Fact]
    public async Task GetTeamingPartners_ValidRequest_ReturnsOk()
    {
        var request = new TeamingPartnerSearchRequest();
        _serviceMock.Setup(s => s.GetTeamingPartnersAsync(request))
            .ReturnsAsync(new PagedResponse<TeamingPartnerDto>());

        var result = await _controller.GetTeamingPartners(request);

        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task GetTeamingPartners_ValidRequest_CallsServiceWithCorrectParameters()
    {
        var request = new TeamingPartnerSearchRequest();
        _serviceMock.Setup(s => s.GetTeamingPartnersAsync(request))
            .ReturnsAsync(new PagedResponse<TeamingPartnerDto>());

        await _controller.GetTeamingPartners(request);

        _serviceMock.Verify(s => s.GetTeamingPartnersAsync(request), Times.Once);
    }

    [Fact]
    public async Task GetTeamingPartners_ValidRequest_ReturnsServiceResult()
    {
        var request = new TeamingPartnerSearchRequest();
        var expected = new PagedResponse<TeamingPartnerDto> { TotalCount = 3 };
        _serviceMock.Setup(s => s.GetTeamingPartnersAsync(request)).ReturnsAsync(expected);

        var result = await _controller.GetTeamingPartners(request) as OkObjectResult;

        result!.Value.Should().Be(expected);
    }
}
