using FedProspector.Api.Controllers;
using FedProspector.Core.DTOs;
using FedProspector.Core.DTOs.Awards;
using FedProspector.Core.Interfaces;
using FluentAssertions;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Moq;

namespace FedProspector.Api.Tests.Controllers;

public class AwardsControllerTests
{
    private readonly Mock<IAwardService> _serviceMock = new();
    private readonly Mock<IExpiringContractService> _expiringServiceMock = new();
    private readonly Mock<IMarketIntelService> _marketIntelServiceMock = new();
    private readonly AwardsController _controller;

    public AwardsControllerTests()
    {
        _controller = new AwardsController(_serviceMock.Object, _expiringServiceMock.Object, _marketIntelServiceMock.Object);
        _controller.ControllerContext = new ControllerContext
        {
            HttpContext = new DefaultHttpContext()
        };
    }

    // --- Search ---

    [Fact]
    public async Task Search_ValidRequest_ReturnsOk()
    {
        var request = new AwardSearchRequest();
        _serviceMock.Setup(s => s.SearchAsync(request))
            .ReturnsAsync(new PagedResponse<AwardSearchDto>());

        var result = await _controller.Search(request);

        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task Search_ValidRequest_CallsServiceWithCorrectParameters()
    {
        var request = new AwardSearchRequest();
        _serviceMock.Setup(s => s.SearchAsync(request))
            .ReturnsAsync(new PagedResponse<AwardSearchDto>());

        await _controller.Search(request);

        _serviceMock.Verify(s => s.SearchAsync(request), Times.Once);
    }

    [Fact]
    public async Task Search_ValidRequest_ReturnsServiceResult()
    {
        var request = new AwardSearchRequest();
        var expected = new PagedResponse<AwardSearchDto> { TotalCount = 15 };
        _serviceMock.Setup(s => s.SearchAsync(request)).ReturnsAsync(expected);

        var result = await _controller.Search(request) as OkObjectResult;

        result!.Value.Should().Be(expected);
    }

    // --- GetBurnRate ---

    [Fact]
    public async Task GetBurnRate_ExistingContract_ReturnsOk()
    {
        _serviceMock.Setup(s => s.GetBurnRateAsync("CONTRACT-001"))
            .ReturnsAsync(new BurnRateDto());

        var result = await _controller.GetBurnRate("CONTRACT-001");

        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task GetBurnRate_NonExistingContract_ReturnsNotFound()
    {
        _serviceMock.Setup(s => s.GetBurnRateAsync("MISSING"))
            .ReturnsAsync((BurnRateDto?)null);

        var result = await _controller.GetBurnRate("MISSING");

        result.Should().BeOfType<NotFoundResult>();
    }

    [Fact]
    public async Task GetBurnRate_CallsServiceWithCorrectContractId()
    {
        _serviceMock.Setup(s => s.GetBurnRateAsync("C-999"))
            .ReturnsAsync(new BurnRateDto());

        await _controller.GetBurnRate("C-999");

        _serviceMock.Verify(s => s.GetBurnRateAsync("C-999"), Times.Once);
    }

    // --- GetDetail ---

    [Fact]
    public async Task GetDetail_ExistingContract_ReturnsOk()
    {
        _serviceMock.Setup(s => s.GetDetailAsync("CONTRACT-001"))
            .ReturnsAsync(new AwardDetailResponse { ContractId = "CONTRACT-001", DataStatus = "full" });

        var result = await _controller.GetDetail("CONTRACT-001");

        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task GetDetail_NonExistingContract_ReturnsOkWithNotLoaded()
    {
        _serviceMock.Setup(s => s.GetDetailAsync("MISSING"))
            .ReturnsAsync(new AwardDetailResponse { ContractId = "MISSING", DataStatus = "not_loaded" });

        var result = await _controller.GetDetail("MISSING");

        result.Should().BeOfType<OkObjectResult>();
        var okResult = (OkObjectResult)result;
        var response = okResult.Value.Should().BeOfType<AwardDetailResponse>().Subject;
        response.DataStatus.Should().Be("not_loaded");
    }

    [Fact]
    public async Task GetDetail_CallsServiceWithCorrectContractId()
    {
        _serviceMock.Setup(s => s.GetDetailAsync("C-ABC"))
            .ReturnsAsync(new AwardDetailResponse { ContractId = "C-ABC" });

        await _controller.GetDetail("C-ABC");

        _serviceMock.Verify(s => s.GetDetailAsync("C-ABC"), Times.Once);
    }
}
