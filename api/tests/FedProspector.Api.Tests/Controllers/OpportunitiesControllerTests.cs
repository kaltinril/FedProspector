using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using FedProspector.Api.Controllers;
using FedProspector.Core.DTOs;
using FedProspector.Core.DTOs.Intelligence;
using FedProspector.Core.DTOs.Opportunities;
using FedProspector.Core.Interfaces;
using FedProspector.Core.Models;
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
    private readonly Mock<IIncumbentVulnerabilityService> _ivsServiceMock = new();
    private readonly Mock<ICompetitorStrengthService> _csiServiceMock = new();
    private readonly Mock<IPartnerCompatibilityService> _pcsServiceMock = new();
    private readonly Mock<IOpenDoorService> _openDoorServiceMock = new();
    private readonly Mock<IPursuitPriorityService> _pursuitPriorityServiceMock = new();
    private readonly Mock<IOpportunityIgnoreService> _ignoreServiceMock = new();
    private readonly OpportunitiesController _controller;

    public OpportunitiesControllerTests()
    {
        _controller = new OpportunitiesController(_serviceMock.Object, _pwinServiceMock.Object, _recommendedServiceMock.Object, _marketIntelServiceMock.Object, _qualificationServiceMock.Object, _attachmentIntelServiceMock.Object, _ivsServiceMock.Object, _csiServiceMock.Object, _pcsServiceMock.Object, _openDoorServiceMock.Object, _pursuitPriorityServiceMock.Object, _ignoreServiceMock.Object);
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
        _serviceMock.Setup(s => s.SearchAsync(request, 10, 1))
            .ReturnsAsync(new PagedResponse<OpportunitySearchDto>());

        var result = await _controller.Search(request);

        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task Search_ValidRequest_CallsServiceWithCorrectParameters()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        var request = new OpportunitySearchRequest();
        _serviceMock.Setup(s => s.SearchAsync(request, 10, 1))
            .ReturnsAsync(new PagedResponse<OpportunitySearchDto>());

        await _controller.Search(request);

        _serviceMock.Verify(s => s.SearchAsync(request, 10, 1), Times.Once);
    }

    [Fact]
    public async Task Search_ValidRequest_ReturnsServiceResult()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        var request = new OpportunitySearchRequest();
        var expected = new PagedResponse<OpportunitySearchDto> { TotalCount = 42 };
        _serviceMock.Setup(s => s.SearchAsync(request, 10, 1)).ReturnsAsync(expected);

        var result = await _controller.Search(request) as OkObjectResult;

        result!.Value.Should().Be(expected);
    }

    [Fact]
    public async Task Search_CallsServiceWithCorrectOrgId()
    {
        SetAuthenticatedUser(userId: 1, orgId: 42);
        var request = new OpportunitySearchRequest();
        _serviceMock.Setup(s => s.SearchAsync(request, 42, 1))
            .ReturnsAsync(new PagedResponse<OpportunitySearchDto>());

        await _controller.Search(request);

        _serviceMock.Verify(s => s.SearchAsync(request, 42, 1), Times.Once);
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
        _serviceMock.Setup(s => s.ExportCsvAsync(request, 99, 1))
            .ReturnsAsync("header1,header2\nval1,val2\n");

        var result = await _controller.ExportCsv(request);

        result.Should().BeOfType<FileContentResult>();
    }

    [Fact]
    public async Task ExportCsv_ReturnsCorrectContentType()
    {
        SetAuthenticatedUser(userId: 1, orgId: 99);
        var request = new OpportunitySearchRequest();
        _serviceMock.Setup(s => s.ExportCsvAsync(request, 99, 1))
            .ReturnsAsync("col1,col2\n");

        var result = await _controller.ExportCsv(request) as FileContentResult;

        result!.ContentType.Should().Be("text/csv");
    }

    [Fact]
    public async Task ExportCsv_ReturnsCorrectFileName()
    {
        SetAuthenticatedUser(userId: 1, orgId: 99);
        var request = new OpportunitySearchRequest();
        _serviceMock.Setup(s => s.ExportCsvAsync(request, 99, 1))
            .ReturnsAsync("col1\n");

        var result = await _controller.ExportCsv(request) as FileContentResult;

        result!.FileDownloadName.Should().Be("opportunities_export.csv");
    }

    [Fact]
    public async Task ExportCsv_CallsServiceWithCorrectParameters()
    {
        SetAuthenticatedUser(userId: 1, orgId: 99);
        var request = new OpportunitySearchRequest { Naics = "541511", Keyword = "cyber" };
        _serviceMock.Setup(s => s.ExportCsvAsync(request, 99, 1))
            .ReturnsAsync("data");

        await _controller.ExportCsv(request);

        _serviceMock.Verify(s => s.ExportCsvAsync(request, 99, 1), Times.Once);
    }

    [Fact]
    public async Task ExportCsv_EmptyCsv_ReturnsFileResult()
    {
        SetAuthenticatedUser(userId: 1, orgId: 99);
        var request = new OpportunitySearchRequest();
        _serviceMock.Setup(s => s.ExportCsvAsync(request, 99, 1))
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
        _recommendedServiceMock.Setup(s => s.GetRecommendedAsync(10, 10, 1))
            .ReturnsAsync(new List<RecommendedOpportunityDto>());

        var result = await _controller.GetRecommended();

        result.Result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task GetRecommended_CustomLimit_CallsServiceWithCorrectLimit()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        _recommendedServiceMock.Setup(s => s.GetRecommendedAsync(10, 25, 1))
            .ReturnsAsync(new List<RecommendedOpportunityDto>());

        await _controller.GetRecommended(limit: 25);

        _recommendedServiceMock.Verify(s => s.GetRecommendedAsync(10, 25, 1), Times.Once);
    }

    [Fact]
    public async Task GetRecommended_ReturnsServiceResult()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        var expected = new List<RecommendedOpportunityDto>
        {
            new() { NoticeId = "REC-001", OqScore = 85.0m, OqScoreCategory = "High" }
        };
        _recommendedServiceMock.Setup(s => s.GetRecommendedAsync(10, 10, 1))
            .ReturnsAsync(expected);

        var result = await _controller.GetRecommended();

        var okResult = result.Result as OkObjectResult;
        okResult!.Value.Should().Be(expected);
    }

    // --- FetchDescription (Phase 123: 429 -> 202 Accepted) ---

    [Fact]
    public async Task FetchDescription_Success_ReturnsOkWithDescriptionText()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        _serviceMock.Setup(s => s.FetchDescriptionAsync("NOTICE-OK", 1))
            .ReturnsAsync(new FetchDescriptionResult("Hello world", null, Success: true));

        var result = await _controller.FetchDescription("NOTICE-OK");

        var ok = result.Should().BeOfType<OkObjectResult>().Subject;
        ok.Value.Should().BeEquivalentTo(new { noticeId = "NOTICE-OK", descriptionText = "Hello world" });
    }

    [Fact]
    public async Task FetchDescription_Queued_Returns202AcceptedWithQueuedPayload()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        _serviceMock.Setup(s => s.FetchDescriptionAsync("NOTICE-429", 1))
            .ReturnsAsync(new FetchDescriptionResult(
                DescriptionText: null,
                ErrorMessage: null,
                Success: false,
                Queued: true,
                QueuedMessage: "Daily quota reached — queued."));

        var result = await _controller.FetchDescription("NOTICE-429");

        var accepted = result.Should().BeOfType<AcceptedResult>().Subject;
        accepted.Value.Should().BeEquivalentTo(new
        {
            noticeId = "NOTICE-429",
            queued = true,
            message = "Daily quota reached — queued."
        });
    }

    [Fact]
    public async Task FetchDescription_NotFound_Returns404()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        _serviceMock.Setup(s => s.FetchDescriptionAsync("MISSING", 1))
            .ReturnsAsync(new FetchDescriptionResult(null, null, Success: false, NotFound: true));

        var result = await _controller.FetchDescription("MISSING");

        result.Should().BeOfType<NotFoundObjectResult>();
    }

    [Fact]
    public async Task FetchDescription_GenericError_Returns502()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        _serviceMock.Setup(s => s.FetchDescriptionAsync("NOTICE-500", 1))
            .ReturnsAsync(new FetchDescriptionResult(null, "SAM.gov returned HTTP 500.", Success: false));

        var result = await _controller.FetchDescription("NOTICE-500");

        var status = result.Should().BeOfType<ObjectResult>().Subject;
        status.StatusCode.Should().Be(502);
    }
}
