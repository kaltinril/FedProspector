using FedProspector.Api.Controllers;
using FedProspector.Core.DTOs;
using FedProspector.Core.DTOs.Entities;
using FedProspector.Core.Interfaces;
using FluentAssertions;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Moq;

namespace FedProspector.Api.Tests.Controllers;

public class EntitiesControllerTests
{
    private readonly Mock<IEntityService> _serviceMock = new();
    private readonly EntitiesController _controller;

    public EntitiesControllerTests()
    {
        _controller = new EntitiesController(_serviceMock.Object);
        _controller.ControllerContext = new ControllerContext
        {
            HttpContext = new DefaultHttpContext()
        };
    }

    // --- Search ---

    [Fact]
    public async Task Search_ValidRequest_ReturnsOk()
    {
        var request = new EntitySearchRequest();
        _serviceMock.Setup(s => s.SearchAsync(request))
            .ReturnsAsync(new PagedResponse<EntitySearchDto>());

        var result = await _controller.Search(request);

        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task Search_ValidRequest_CallsServiceWithCorrectParameters()
    {
        var request = new EntitySearchRequest();
        _serviceMock.Setup(s => s.SearchAsync(request))
            .ReturnsAsync(new PagedResponse<EntitySearchDto>());

        await _controller.Search(request);

        _serviceMock.Verify(s => s.SearchAsync(request), Times.Once);
    }

    [Fact]
    public async Task Search_ValidRequest_ReturnsServiceResult()
    {
        var request = new EntitySearchRequest();
        var expected = new PagedResponse<EntitySearchDto> { TotalCount = 7 };
        _serviceMock.Setup(s => s.SearchAsync(request)).ReturnsAsync(expected);

        var result = await _controller.Search(request) as OkObjectResult;

        result!.Value.Should().Be(expected);
    }

    // --- GetCompetitorProfile ---

    [Fact]
    public async Task GetCompetitorProfile_ExistingUei_ReturnsOk()
    {
        _serviceMock.Setup(s => s.GetCompetitorProfileAsync("UEI123"))
            .ReturnsAsync(new CompetitorProfileDto());

        var result = await _controller.GetCompetitorProfile("UEI123");

        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task GetCompetitorProfile_NonExistingUei_ReturnsNotFound()
    {
        _serviceMock.Setup(s => s.GetCompetitorProfileAsync("MISSING"))
            .ReturnsAsync((CompetitorProfileDto?)null);

        var result = await _controller.GetCompetitorProfile("MISSING");

        result.Should().BeOfType<NotFoundResult>();
    }

    [Fact]
    public async Task GetCompetitorProfile_CallsServiceWithCorrectUei()
    {
        _serviceMock.Setup(s => s.GetCompetitorProfileAsync("ABC"))
            .ReturnsAsync(new CompetitorProfileDto());

        await _controller.GetCompetitorProfile("ABC");

        _serviceMock.Verify(s => s.GetCompetitorProfileAsync("ABC"), Times.Once);
    }

    // --- CheckExclusion ---

    [Fact]
    public async Task CheckExclusion_AnyUei_ReturnsOk()
    {
        _serviceMock.Setup(s => s.CheckExclusionAsync("UEI456"))
            .ReturnsAsync(new ExclusionCheckDto());

        var result = await _controller.CheckExclusion("UEI456");

        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task CheckExclusion_CallsServiceWithCorrectUei()
    {
        _serviceMock.Setup(s => s.CheckExclusionAsync("XYZ"))
            .ReturnsAsync(new ExclusionCheckDto());

        await _controller.CheckExclusion("XYZ");

        _serviceMock.Verify(s => s.CheckExclusionAsync("XYZ"), Times.Once);
    }

    // --- GetDetail ---

    [Fact]
    public async Task GetDetail_ExistingUei_ReturnsOk()
    {
        _serviceMock.Setup(s => s.GetDetailAsync("UEI789"))
            .ReturnsAsync(new EntityDetailDto());

        var result = await _controller.GetDetail("UEI789");

        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task GetDetail_NonExistingUei_ReturnsNotFound()
    {
        _serviceMock.Setup(s => s.GetDetailAsync("NOPE"))
            .ReturnsAsync((EntityDetailDto?)null);

        var result = await _controller.GetDetail("NOPE");

        result.Should().BeOfType<NotFoundResult>();
    }

    [Fact]
    public async Task GetDetail_CallsServiceWithCorrectUei()
    {
        _serviceMock.Setup(s => s.GetDetailAsync("UEI-TEST"))
            .ReturnsAsync(new EntityDetailDto());

        await _controller.GetDetail("UEI-TEST");

        _serviceMock.Verify(s => s.GetDetailAsync("UEI-TEST"), Times.Once);
    }
}
