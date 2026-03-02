using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using FedProspector.Api.Controllers;
using FedProspector.Core.DTOs;
using FedProspector.Core.DTOs.Opportunities;
using FedProspector.Core.Interfaces;
using FluentAssertions;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Moq;

namespace FedProspector.Api.Tests.Controllers;

public class OpportunitiesControllerTests
{
    private readonly Mock<IOpportunityService> _serviceMock = new();
    private readonly OpportunitiesController _controller;

    public OpportunitiesControllerTests()
    {
        _controller = new OpportunitiesController(_serviceMock.Object);
        _controller.ControllerContext = new ControllerContext
        {
            HttpContext = new DefaultHttpContext()
        };
    }

    // --- Search ---

    [Fact]
    public async Task Search_ValidRequest_ReturnsOk()
    {
        var request = new OpportunitySearchRequest();
        _serviceMock.Setup(s => s.SearchAsync(request))
            .ReturnsAsync(new PagedResponse<OpportunitySearchDto>());

        var result = await _controller.Search(request);

        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task Search_ValidRequest_CallsServiceWithCorrectParameters()
    {
        var request = new OpportunitySearchRequest();
        _serviceMock.Setup(s => s.SearchAsync(request))
            .ReturnsAsync(new PagedResponse<OpportunitySearchDto>());

        await _controller.Search(request);

        _serviceMock.Verify(s => s.SearchAsync(request), Times.Once);
    }

    [Fact]
    public async Task Search_ValidRequest_ReturnsServiceResult()
    {
        var request = new OpportunitySearchRequest();
        var expected = new PagedResponse<OpportunitySearchDto> { TotalCount = 42 };
        _serviceMock.Setup(s => s.SearchAsync(request)).ReturnsAsync(expected);

        var result = await _controller.Search(request) as OkObjectResult;

        result!.Value.Should().Be(expected);
    }

    // --- GetTargets ---

    [Fact]
    public async Task GetTargets_ValidRequest_ReturnsOk()
    {
        var request = new TargetOpportunitySearchRequest();
        _serviceMock.Setup(s => s.GetTargetsAsync(request))
            .ReturnsAsync(new PagedResponse<TargetOpportunityDto>());

        var result = await _controller.GetTargets(request);

        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task GetTargets_ValidRequest_CallsServiceWithCorrectParameters()
    {
        var request = new TargetOpportunitySearchRequest();
        _serviceMock.Setup(s => s.GetTargetsAsync(request))
            .ReturnsAsync(new PagedResponse<TargetOpportunityDto>());

        await _controller.GetTargets(request);

        _serviceMock.Verify(s => s.GetTargetsAsync(request), Times.Once);
    }

    // --- GetDetail ---

    [Fact]
    public async Task GetDetail_ExistingNoticeId_ReturnsOk()
    {
        _serviceMock.Setup(s => s.GetDetailAsync("NOTICE-001"))
            .ReturnsAsync(new OpportunityDetailDto());

        var result = await _controller.GetDetail("NOTICE-001");

        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task GetDetail_NonExistingNoticeId_ReturnsNotFound()
    {
        _serviceMock.Setup(s => s.GetDetailAsync("DOES-NOT-EXIST"))
            .ReturnsAsync((OpportunityDetailDto?)null);

        var result = await _controller.GetDetail("DOES-NOT-EXIST");

        result.Should().BeOfType<NotFoundResult>();
    }

    [Fact]
    public async Task GetDetail_ExistingNoticeId_CallsServiceWithCorrectId()
    {
        _serviceMock.Setup(s => s.GetDetailAsync("ABC-123"))
            .ReturnsAsync(new OpportunityDetailDto());

        await _controller.GetDetail("ABC-123");

        _serviceMock.Verify(s => s.GetDetailAsync("ABC-123"), Times.Once);
    }

    // --- ExportCsv ---

    [Fact]
    public async Task ExportCsv_ValidRequest_ReturnsFileResult()
    {
        var request = new OpportunitySearchRequest { SetAside = "WOSB" };
        _serviceMock.Setup(s => s.ExportCsvAsync(request))
            .ReturnsAsync("header1,header2\nval1,val2\n");

        var result = await _controller.ExportCsv(request);

        result.Should().BeOfType<FileContentResult>();
    }

    [Fact]
    public async Task ExportCsv_ReturnsCorrectContentType()
    {
        var request = new OpportunitySearchRequest();
        _serviceMock.Setup(s => s.ExportCsvAsync(request))
            .ReturnsAsync("col1,col2\n");

        var result = await _controller.ExportCsv(request) as FileContentResult;

        result!.ContentType.Should().Be("text/csv");
    }

    [Fact]
    public async Task ExportCsv_ReturnsCorrectFileName()
    {
        var request = new OpportunitySearchRequest();
        _serviceMock.Setup(s => s.ExportCsvAsync(request))
            .ReturnsAsync("col1\n");

        var result = await _controller.ExportCsv(request) as FileContentResult;

        result!.FileDownloadName.Should().Be("opportunities_export.csv");
    }

    [Fact]
    public async Task ExportCsv_CallsServiceWithCorrectParameters()
    {
        var request = new OpportunitySearchRequest { Naics = "541511", Keyword = "cyber" };
        _serviceMock.Setup(s => s.ExportCsvAsync(request))
            .ReturnsAsync("data");

        await _controller.ExportCsv(request);

        _serviceMock.Verify(s => s.ExportCsvAsync(request), Times.Once);
    }

    [Fact]
    public async Task ExportCsv_EmptyCsv_ReturnsFileResult()
    {
        var request = new OpportunitySearchRequest();
        _serviceMock.Setup(s => s.ExportCsvAsync(request))
            .ReturnsAsync(string.Empty);

        var result = await _controller.ExportCsv(request);

        result.Should().BeOfType<FileContentResult>();
    }
}
