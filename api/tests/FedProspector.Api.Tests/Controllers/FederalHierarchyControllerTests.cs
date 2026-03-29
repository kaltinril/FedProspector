using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using FedProspector.Api.Controllers;
using FedProspector.Core.DTOs;
using FedProspector.Core.DTOs.FederalHierarchy;
using FedProspector.Core.DTOs.Opportunities;
using FedProspector.Core.Interfaces;
using FluentAssertions;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Moq;

namespace FedProspector.Api.Tests.Controllers;

public class FederalHierarchyControllerTests
{
    private readonly Mock<IFederalHierarchyService> _serviceMock = new();
    private readonly FederalHierarchyController _controller;

    public FederalHierarchyControllerTests()
    {
        _controller = new FederalHierarchyController(_serviceMock.Object);
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
    public async Task Search_ValidRequest_ReturnsOk()
    {
        var request = new FederalOrgSearchRequestDto();
        _serviceMock.Setup(s => s.SearchAsync(request))
            .ReturnsAsync(new PagedResponse<FederalOrgListItemDto>());

        var result = await _controller.Search(request);

        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task Search_ValidRequest_CallsServiceWithCorrectParameters()
    {
        var request = new FederalOrgSearchRequestDto { Keyword = "defense", Level = 1 };
        _serviceMock.Setup(s => s.SearchAsync(request))
            .ReturnsAsync(new PagedResponse<FederalOrgListItemDto>());

        await _controller.Search(request);

        _serviceMock.Verify(s => s.SearchAsync(request), Times.Once);
    }

    [Fact]
    public async Task Search_ValidRequest_ReturnsServiceResult()
    {
        var request = new FederalOrgSearchRequestDto();
        var expected = new PagedResponse<FederalOrgListItemDto> { TotalCount = 15 };
        _serviceMock.Setup(s => s.SearchAsync(request)).ReturnsAsync(expected);

        var result = await _controller.Search(request) as OkObjectResult;

        result!.Value.Should().Be(expected);
    }

    [Fact]
    public async Task Search_WithFilters_PassesAllFiltersToService()
    {
        var request = new FederalOrgSearchRequestDto
        {
            Keyword = "army",
            FhOrgType = "Department/Ind. Agency",
            Status = "ACTIVE",
            AgencyCode = "097",
            Cgac = "021",
            Level = 2,
            ParentOrgId = 100
        };
        _serviceMock.Setup(s => s.SearchAsync(request))
            .ReturnsAsync(new PagedResponse<FederalOrgListItemDto>());

        await _controller.Search(request);

        _serviceMock.Verify(s => s.SearchAsync(request), Times.Once);
    }

    // --- GetDetail ---

    [Fact]
    public async Task GetDetail_ExistingOrg_ReturnsOk()
    {
        _serviceMock.Setup(s => s.GetDetailAsync(42))
            .ReturnsAsync(new FederalOrgDetailDto { FhOrgId = 42, FhOrgName = "Dept of Defense" });

        var result = await _controller.GetDetail(42);

        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task GetDetail_ExistingOrg_ReturnsServiceResult()
    {
        var expected = new FederalOrgDetailDto { FhOrgId = 42, FhOrgName = "Dept of Defense" };
        _serviceMock.Setup(s => s.GetDetailAsync(42)).ReturnsAsync(expected);

        var result = await _controller.GetDetail(42) as OkObjectResult;

        result!.Value.Should().Be(expected);
    }

    [Fact]
    public async Task GetDetail_NonExistingOrg_ReturnsNotFound()
    {
        _serviceMock.Setup(s => s.GetDetailAsync(999999))
            .ReturnsAsync((FederalOrgDetailDto?)null);

        var result = await _controller.GetDetail(999999);

        result.Should().BeOfType<NotFoundResult>();
    }

    [Fact]
    public async Task GetDetail_CallsServiceWithCorrectFhOrgId()
    {
        _serviceMock.Setup(s => s.GetDetailAsync(123))
            .ReturnsAsync(new FederalOrgDetailDto());

        await _controller.GetDetail(123);

        _serviceMock.Verify(s => s.GetDetailAsync(123), Times.Once);
    }

    // --- GetChildren ---

    [Fact]
    public async Task GetChildren_ValidRequest_ReturnsOk()
    {
        _serviceMock.Setup(s => s.GetChildrenAsync(10, null, null))
            .ReturnsAsync(new List<FederalOrgListItemDto>());

        var result = await _controller.GetChildren(10);

        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task GetChildren_ReturnsServiceResult()
    {
        var expected = new List<FederalOrgListItemDto>
        {
            new() { FhOrgId = 20, FhOrgName = "Sub Agency A" },
            new() { FhOrgId = 21, FhOrgName = "Sub Agency B" }
        };
        _serviceMock.Setup(s => s.GetChildrenAsync(10, null, null)).ReturnsAsync(expected);

        var result = await _controller.GetChildren(10) as OkObjectResult;

        result!.Value.Should().Be(expected);
    }

    [Fact]
    public async Task GetChildren_WithStatusFilter_PassesStatusToService()
    {
        _serviceMock.Setup(s => s.GetChildrenAsync(10, "ACTIVE", null))
            .ReturnsAsync(new List<FederalOrgListItemDto>());

        await _controller.GetChildren(10, status: "ACTIVE");

        _serviceMock.Verify(s => s.GetChildrenAsync(10, "ACTIVE", null), Times.Once);
    }

    [Fact]
    public async Task GetChildren_WithKeywordFilter_PassesKeywordToService()
    {
        _serviceMock.Setup(s => s.GetChildrenAsync(10, null, "logistics"))
            .ReturnsAsync(new List<FederalOrgListItemDto>());

        await _controller.GetChildren(10, keyword: "logistics");

        _serviceMock.Verify(s => s.GetChildrenAsync(10, null, "logistics"), Times.Once);
    }

    [Fact]
    public async Task GetChildren_WithBothFilters_PassesBothToService()
    {
        _serviceMock.Setup(s => s.GetChildrenAsync(10, "ACTIVE", "logistics"))
            .ReturnsAsync(new List<FederalOrgListItemDto>());

        await _controller.GetChildren(10, status: "ACTIVE", keyword: "logistics");

        _serviceMock.Verify(s => s.GetChildrenAsync(10, "ACTIVE", "logistics"), Times.Once);
    }

    // --- GetTree ---

    [Fact]
    public async Task GetTree_NoKeyword_ReturnsOk()
    {
        _serviceMock.Setup(s => s.GetTreeAsync(null))
            .ReturnsAsync(new List<FederalOrgTreeNodeDto>());

        var result = await _controller.GetTree();

        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task GetTree_ReturnsServiceResult()
    {
        var expected = new List<FederalOrgTreeNodeDto>
        {
            new() { FhOrgId = 1, FhOrgName = "Dept of Defense", ChildCount = 5, DescendantCount = 200 },
            new() { FhOrgId = 2, FhOrgName = "Dept of Energy", ChildCount = 3, DescendantCount = 50 }
        };
        _serviceMock.Setup(s => s.GetTreeAsync(null)).ReturnsAsync(expected);

        var result = await _controller.GetTree() as OkObjectResult;

        result!.Value.Should().Be(expected);
    }

    [Fact]
    public async Task GetTree_WithKeyword_PassesKeywordToService()
    {
        _serviceMock.Setup(s => s.GetTreeAsync("defense"))
            .ReturnsAsync(new List<FederalOrgTreeNodeDto>());

        await _controller.GetTree(keyword: "defense");

        _serviceMock.Verify(s => s.GetTreeAsync("defense"), Times.Once);
    }

    // --- GetOpportunities ---

    [Fact]
    public async Task GetOpportunities_ValidRequest_ReturnsOk()
    {
        var pagedRequest = new PagedRequest();
        _serviceMock.Setup(s => s.GetOpportunitiesAsync(42, pagedRequest, null, null, null))
            .ReturnsAsync(new PagedResponse<OpportunitySearchDto>());

        var result = await _controller.GetOpportunities(42, pagedRequest);

        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task GetOpportunities_ReturnsServiceResult()
    {
        var pagedRequest = new PagedRequest();
        var expected = new PagedResponse<OpportunitySearchDto> { TotalCount = 7 };
        _serviceMock.Setup(s => s.GetOpportunitiesAsync(42, pagedRequest, null, null, null))
            .ReturnsAsync(expected);

        var result = await _controller.GetOpportunities(42, pagedRequest) as OkObjectResult;

        result!.Value.Should().Be(expected);
    }

    [Fact]
    public async Task GetOpportunities_WithFilters_PassesAllFiltersToService()
    {
        var pagedRequest = new PagedRequest();
        _serviceMock.Setup(s => s.GetOpportunitiesAsync(42, pagedRequest, "true", "Solicitation", "WOSB"))
            .ReturnsAsync(new PagedResponse<OpportunitySearchDto>());

        await _controller.GetOpportunities(42, pagedRequest, active: "true", type: "Solicitation", setAsideCode: "WOSB");

        _serviceMock.Verify(s => s.GetOpportunitiesAsync(42, pagedRequest, "true", "Solicitation", "WOSB"), Times.Once);
    }

    [Fact]
    public async Task GetOpportunities_CallsServiceWithCorrectFhOrgId()
    {
        var pagedRequest = new PagedRequest();
        _serviceMock.Setup(s => s.GetOpportunitiesAsync(999, pagedRequest, null, null, null))
            .ReturnsAsync(new PagedResponse<OpportunitySearchDto>());

        await _controller.GetOpportunities(999, pagedRequest);

        _serviceMock.Verify(s => s.GetOpportunitiesAsync(999, pagedRequest, null, null, null), Times.Once);
    }

    // --- TriggerRefresh ---

    [Fact]
    public void TriggerRefresh_ValidHierarchyLevel_Returns501()
    {
        SetAuthenticatedUser();
        var request = new HierarchyRefreshRequestDto { Level = "hierarchy", ApiKey = 2 };

        var result = _controller.TriggerRefresh(request);

        result.Should().BeOfType<ObjectResult>();
        var objectResult = result as ObjectResult;
        objectResult!.StatusCode.Should().Be(501);
    }

    [Fact]
    public void TriggerRefresh_ValidOfficesLevel_Returns501()
    {
        SetAuthenticatedUser();
        var request = new HierarchyRefreshRequestDto { Level = "offices", ApiKey = 1 };

        var result = _controller.TriggerRefresh(request);

        var objectResult = result as ObjectResult;
        objectResult!.StatusCode.Should().Be(501);
    }

    [Fact]
    public void TriggerRefresh_ValidFullLevel_Returns501()
    {
        SetAuthenticatedUser();
        var request = new HierarchyRefreshRequestDto { Level = "full", ApiKey = 2 };

        var result = _controller.TriggerRefresh(request);

        var objectResult = result as ObjectResult;
        objectResult!.StatusCode.Should().Be(501);
    }

    [Fact]
    public void TriggerRefresh_InvalidLevel_ReturnsBadRequest()
    {
        SetAuthenticatedUser();
        var request = new HierarchyRefreshRequestDto { Level = "invalid", ApiKey = 2 };

        var result = _controller.TriggerRefresh(request);

        result.Should().BeOfType<BadRequestObjectResult>();
    }

    [Fact]
    public void TriggerRefresh_InvalidApiKey_ReturnsBadRequest()
    {
        SetAuthenticatedUser();
        var request = new HierarchyRefreshRequestDto { Level = "hierarchy", ApiKey = 3 };

        var result = _controller.TriggerRefresh(request);

        result.Should().BeOfType<BadRequestObjectResult>();
    }

    [Fact]
    public void TriggerRefresh_ApiKeyZero_ReturnsBadRequest()
    {
        SetAuthenticatedUser();
        var request = new HierarchyRefreshRequestDto { Level = "hierarchy", ApiKey = 0 };

        var result = _controller.TriggerRefresh(request);

        result.Should().BeOfType<BadRequestObjectResult>();
    }

    [Fact]
    public void TriggerRefresh_InvalidLevelCheckedBeforeApiKey()
    {
        SetAuthenticatedUser();
        var request = new HierarchyRefreshRequestDto { Level = "bogus", ApiKey = 99 };

        var result = _controller.TriggerRefresh(request);

        // Level validation runs first in the controller
        result.Should().BeOfType<BadRequestObjectResult>();
        var badRequest = result as BadRequestObjectResult;
        badRequest!.Value.Should().Be("Level must be 'hierarchy', 'offices', or 'full'.");
    }

    // --- GetRefreshStatus ---

    [Fact]
    public async Task GetRefreshStatus_ReturnsOk()
    {
        _serviceMock.Setup(s => s.GetRefreshStatusAsync())
            .ReturnsAsync(new HierarchyRefreshStatusDto());

        var result = await _controller.GetRefreshStatus();

        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task GetRefreshStatus_ReturnsServiceResult()
    {
        var expected = new HierarchyRefreshStatusDto
        {
            IsRunning = false,
            LastRefreshAt = new DateTime(2026, 3, 28, 10, 0, 0),
            LastRefreshRecordCount = 5000,
            JobId = 42
        };
        _serviceMock.Setup(s => s.GetRefreshStatusAsync()).ReturnsAsync(expected);

        var result = await _controller.GetRefreshStatus() as OkObjectResult;

        result!.Value.Should().Be(expected);
    }

    [Fact]
    public async Task GetRefreshStatus_CallsServiceOnce()
    {
        _serviceMock.Setup(s => s.GetRefreshStatusAsync())
            .ReturnsAsync(new HierarchyRefreshStatusDto());

        await _controller.GetRefreshStatus();

        _serviceMock.Verify(s => s.GetRefreshStatusAsync(), Times.Once);
    }
}
