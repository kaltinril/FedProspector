using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using FedProspector.Api.Controllers;
using FedProspector.Core.DTOs;
using FedProspector.Core.DTOs.Intelligence;
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
    private readonly Mock<IPWinService> _pwinServiceMock = new();
    private readonly Mock<IRecommendedOpportunityService> _recommendedServiceMock = new();
    private readonly Mock<IMarketIntelService> _marketIntelServiceMock = new();
    private readonly Mock<IQualificationService> _qualificationServiceMock = new();
    private readonly Mock<IAttachmentIntelService> _attachmentIntelServiceMock = new();
    private readonly OpportunitiesController _controller;

    public OpportunitiesControllerTests()
    {
        _controller = new OpportunitiesController(_serviceMock.Object, _pwinServiceMock.Object, _recommendedServiceMock.Object, _marketIntelServiceMock.Object, _qualificationServiceMock.Object, _attachmentIntelServiceMock.Object);
        _controller.ControllerContext = new ControllerContext
        {
            HttpContext = new DefaultHttpContext()
        };
    }

    private static ClaimsPrincipal CreateUser(int userId = 1, string role = "user", bool isOrgAdmin = false, int orgId = 1)
    {
        var claims = new List<Claim>
        {
            new(JwtRegisteredClaimNames.Sub, userId.ToString()),
            new(ClaimTypes.NameIdentifier, userId.ToString()),
            new(ClaimTypes.Role, role),
            new("is_org_admin", isOrgAdmin.ToString().ToLower()),
            new("org_id", orgId.ToString())
        };
        return new ClaimsPrincipal(new ClaimsIdentity(claims, "TestAuth"));
    }

    private void SetAuthenticatedUser(int userId = 1, int orgId = 1)
    {
        _controller.ControllerContext.HttpContext.User = CreateUser(userId, orgId: orgId);
    }

    // --- Search ---

    [Fact]
    public async Task Search_NoOrgId_ReturnsUnauthorized()
    {
        var request = new OpportunitySearchRequest();

        var result = await _controller.Search(request);

        result.Should().BeOfType<UnauthorizedResult>();
    }

    [Fact]
    public async Task Search_ValidRequest_ReturnsOk()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        var request = new OpportunitySearchRequest();
        _serviceMock.Setup(s => s.SearchAsync(request, 10))
            .ReturnsAsync(new PagedResponse<OpportunitySearchDto>());

        var result = await _controller.Search(request);

        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task Search_ValidRequest_CallsServiceWithCorrectParameters()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        var request = new OpportunitySearchRequest();
        _serviceMock.Setup(s => s.SearchAsync(request, 10))
            .ReturnsAsync(new PagedResponse<OpportunitySearchDto>());

        await _controller.Search(request);

        _serviceMock.Verify(s => s.SearchAsync(request, 10), Times.Once);
    }

    [Fact]
    public async Task Search_ValidRequest_ReturnsServiceResult()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        var request = new OpportunitySearchRequest();
        var expected = new PagedResponse<OpportunitySearchDto> { TotalCount = 42 };
        _serviceMock.Setup(s => s.SearchAsync(request, 10)).ReturnsAsync(expected);

        var result = await _controller.Search(request) as OkObjectResult;

        result!.Value.Should().Be(expected);
    }

    [Fact]
    public async Task Search_CallsServiceWithCorrectOrgId()
    {
        SetAuthenticatedUser(userId: 1, orgId: 42);
        var request = new OpportunitySearchRequest();
        _serviceMock.Setup(s => s.SearchAsync(request, 42))
            .ReturnsAsync(new PagedResponse<OpportunitySearchDto>());

        await _controller.Search(request);

        _serviceMock.Verify(s => s.SearchAsync(request, 42), Times.Once);
    }

    // --- GetTargets ---

    [Fact]
    public async Task GetTargets_NoOrgId_ReturnsUnauthorized()
    {
        var request = new TargetOpportunitySearchRequest();

        var result = await _controller.GetTargets(request);

        result.Should().BeOfType<UnauthorizedResult>();
    }

    [Fact]
    public async Task GetTargets_ValidRequest_ReturnsOk()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        var request = new TargetOpportunitySearchRequest();
        _serviceMock.Setup(s => s.GetTargetsAsync(request, 10))
            .ReturnsAsync(new PagedResponse<TargetOpportunityDto>());

        var result = await _controller.GetTargets(request);

        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task GetTargets_ValidRequest_CallsServiceWithCorrectParameters()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        var request = new TargetOpportunitySearchRequest();
        _serviceMock.Setup(s => s.GetTargetsAsync(request, 10))
            .ReturnsAsync(new PagedResponse<TargetOpportunityDto>());

        await _controller.GetTargets(request);

        _serviceMock.Verify(s => s.GetTargetsAsync(request, 10), Times.Once);
    }

    // --- GetDetail ---

    [Fact]
    public async Task GetDetail_NoOrgId_ReturnsUnauthorized()
    {
        var result = await _controller.GetDetail("NOTICE-001");

        result.Should().BeOfType<UnauthorizedResult>();
    }

    [Fact]
    public async Task GetDetail_ExistingNoticeId_ReturnsOk()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        _serviceMock.Setup(s => s.GetDetailAsync("NOTICE-001", 10))
            .ReturnsAsync(new OpportunityDetailDto());

        var result = await _controller.GetDetail("NOTICE-001");

        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task GetDetail_NonExistingNoticeId_ReturnsNotFound()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        _serviceMock.Setup(s => s.GetDetailAsync("DOES-NOT-EXIST", 10))
            .ReturnsAsync((OpportunityDetailDto?)null);

        var result = await _controller.GetDetail("DOES-NOT-EXIST");

        result.Should().BeOfType<NotFoundResult>();
    }

    [Fact]
    public async Task GetDetail_ExistingNoticeId_CallsServiceWithCorrectId()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        _serviceMock.Setup(s => s.GetDetailAsync("ABC-123", 10))
            .ReturnsAsync(new OpportunityDetailDto());

        await _controller.GetDetail("ABC-123");

        _serviceMock.Verify(s => s.GetDetailAsync("ABC-123", 10), Times.Once);
    }

    [Fact]
    public async Task GetDetail_CallsServiceWithCorrectOrgId()
    {
        SetAuthenticatedUser(userId: 1, orgId: 99);
        _serviceMock.Setup(s => s.GetDetailAsync("ABC-123", 99))
            .ReturnsAsync(new OpportunityDetailDto());

        await _controller.GetDetail("ABC-123");

        _serviceMock.Verify(s => s.GetDetailAsync("ABC-123", 99), Times.Once);
    }

    // --- ExportCsv ---

    [Fact]
    public async Task ExportCsv_NoOrgId_ReturnsUnauthorized()
    {
        var request = new OpportunitySearchRequest();

        var result = await _controller.ExportCsv(request);

        result.Should().BeOfType<UnauthorizedResult>();
    }

    [Fact]
    public async Task ExportCsv_ValidRequest_ReturnsFileResult()
    {
        SetAuthenticatedUser(userId: 1, orgId: 99);
        var request = new OpportunitySearchRequest { SetAside = "WOSB" };
        _serviceMock.Setup(s => s.ExportCsvAsync(request, 99))
            .ReturnsAsync("header1,header2\nval1,val2\n");

        var result = await _controller.ExportCsv(request);

        result.Should().BeOfType<FileContentResult>();
    }

    [Fact]
    public async Task ExportCsv_ReturnsCorrectContentType()
    {
        SetAuthenticatedUser(userId: 1, orgId: 99);
        var request = new OpportunitySearchRequest();
        _serviceMock.Setup(s => s.ExportCsvAsync(request, 99))
            .ReturnsAsync("col1,col2\n");

        var result = await _controller.ExportCsv(request) as FileContentResult;

        result!.ContentType.Should().Be("text/csv");
    }

    [Fact]
    public async Task ExportCsv_ReturnsCorrectFileName()
    {
        SetAuthenticatedUser(userId: 1, orgId: 99);
        var request = new OpportunitySearchRequest();
        _serviceMock.Setup(s => s.ExportCsvAsync(request, 99))
            .ReturnsAsync("col1\n");

        var result = await _controller.ExportCsv(request) as FileContentResult;

        result!.FileDownloadName.Should().Be("opportunities_export.csv");
    }

    [Fact]
    public async Task ExportCsv_CallsServiceWithCorrectParameters()
    {
        SetAuthenticatedUser(userId: 1, orgId: 99);
        var request = new OpportunitySearchRequest { Naics = "541511", Keyword = "cyber" };
        _serviceMock.Setup(s => s.ExportCsvAsync(request, 99))
            .ReturnsAsync("data");

        await _controller.ExportCsv(request);

        _serviceMock.Verify(s => s.ExportCsvAsync(request, 99), Times.Once);
    }

    [Fact]
    public async Task ExportCsv_EmptyCsv_ReturnsFileResult()
    {
        SetAuthenticatedUser(userId: 1, orgId: 99);
        var request = new OpportunitySearchRequest();
        _serviceMock.Setup(s => s.ExportCsvAsync(request, 99))
            .ReturnsAsync(string.Empty);

        var result = await _controller.ExportCsv(request);

        result.Should().BeOfType<FileContentResult>();
    }

    // --- GetRecommended ---

    [Fact]
    public async Task GetRecommended_NoOrgId_ReturnsUnauthorized()
    {
        var result = await _controller.GetRecommended();

        result.Result.Should().BeOfType<UnauthorizedResult>();
    }

    [Fact]
    public async Task GetRecommended_ValidRequest_ReturnsOk()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        _recommendedServiceMock.Setup(s => s.GetRecommendedAsync(10, 10))
            .ReturnsAsync(new List<RecommendedOpportunityDto>());

        var result = await _controller.GetRecommended();

        result.Result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task GetRecommended_CustomLimit_CallsServiceWithCorrectLimit()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        _recommendedServiceMock.Setup(s => s.GetRecommendedAsync(10, 25))
            .ReturnsAsync(new List<RecommendedOpportunityDto>());

        await _controller.GetRecommended(limit: 25);

        _recommendedServiceMock.Verify(s => s.GetRecommendedAsync(10, 25), Times.Once);
    }

    [Fact]
    public async Task GetRecommended_ReturnsServiceResult()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        var expected = new List<RecommendedOpportunityDto>
        {
            new() { NoticeId = "REC-001", QScore = 85.0m, QScoreCategory = "High" }
        };
        _recommendedServiceMock.Setup(s => s.GetRecommendedAsync(10, 10))
            .ReturnsAsync(expected);

        var result = await _controller.GetRecommended();

        var okResult = result.Result as OkObjectResult;
        okResult!.Value.Should().Be(expected);
    }
}
