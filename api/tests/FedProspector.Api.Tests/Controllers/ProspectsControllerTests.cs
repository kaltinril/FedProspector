using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using FedProspector.Api.Controllers;
using FedProspector.Core.DTOs;
using FedProspector.Core.DTOs.Prospects;
using FedProspector.Core.Interfaces;
using FedProspector.Core.Models;
using FedProspector.Infrastructure.Data;
using FluentAssertions;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Moq;

namespace FedProspector.Api.Tests.Controllers;

public class ProspectsControllerTests
{
    private readonly Mock<IProspectService> _serviceMock = new();
    private readonly ProspectsController _controller;

    public ProspectsControllerTests()
    {
        _controller = new ProspectsController(_serviceMock.Object);
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

    // --- Search (org-scoped) ---

    [Fact]
    public async Task Search_NoUser_ReturnsUnauthorized()
    {
        var request = new ProspectSearchRequest();

        var result = await _controller.Search(request);

        result.Should().BeOfType<UnauthorizedResult>();
    }

    [Fact]
    public async Task Search_AuthenticatedUser_ReturnsOk()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        var request = new ProspectSearchRequest();
        _serviceMock.Setup(s => s.SearchAsync(10, request))
            .ReturnsAsync(new PagedResponse<ProspectListDto>());

        var result = await _controller.Search(request);

        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task Search_CallsServiceWithCorrectOrgId()
    {
        SetAuthenticatedUser(userId: 1, orgId: 42);
        var request = new ProspectSearchRequest();
        _serviceMock.Setup(s => s.SearchAsync(42, request))
            .ReturnsAsync(new PagedResponse<ProspectListDto>());

        await _controller.Search(request);

        _serviceMock.Verify(s => s.SearchAsync(42, request), Times.Once);
    }

    [Fact]
    public async Task Search_DifferentOrg_PassesDifferentOrgIdToService()
    {
        SetAuthenticatedUser(userId: 1, orgId: 99);
        var request = new ProspectSearchRequest();
        _serviceMock.Setup(s => s.SearchAsync(99, request))
            .ReturnsAsync(new PagedResponse<ProspectListDto>());

        await _controller.Search(request);

        _serviceMock.Verify(s => s.SearchAsync(99, request), Times.Once);
        _serviceMock.Verify(s => s.SearchAsync(It.Is<int>(id => id != 99), It.IsAny<ProspectSearchRequest>()), Times.Never);
    }

    // --- GetDetail (org-scoped) ---

    [Fact]
    public async Task GetDetail_NoUser_ReturnsUnauthorized()
    {
        var result = await _controller.GetDetail(1);

        result.Should().BeOfType<UnauthorizedResult>();
    }

    [Fact]
    public async Task GetDetail_ExistingProspect_ReturnsOk()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        _serviceMock.Setup(s => s.GetDetailAsync(10, 5))
            .ReturnsAsync(new ProspectDetailDto());

        var result = await _controller.GetDetail(5);

        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task GetDetail_NonExistingProspect_ReturnsNotFound()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        _serviceMock.Setup(s => s.GetDetailAsync(10, 999))
            .ReturnsAsync((ProspectDetailDto?)null);

        var result = await _controller.GetDetail(999);

        result.Should().BeOfType<NotFoundResult>();
    }

    [Fact]
    public async Task GetDetail_CallsServiceWithCorrectOrgIdAndProspectId()
    {
        SetAuthenticatedUser(userId: 1, orgId: 15);
        _serviceMock.Setup(s => s.GetDetailAsync(15, 7))
            .ReturnsAsync(new ProspectDetailDto());

        await _controller.GetDetail(7);

        _serviceMock.Verify(s => s.GetDetailAsync(15, 7), Times.Once);
    }

    // --- Create (org-scoped) ---

    [Fact]
    public async Task Create_NoUser_ReturnsUnauthorized()
    {
        var request = new CreateProspectRequest();

        var result = await _controller.Create(request);

        result.Should().BeOfType<UnauthorizedResult>();
    }

    [Fact]
    public async Task Create_AuthenticatedUser_ReturnsCreatedAtAction()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        var request = new CreateProspectRequest { NoticeId = "NOTICE-001" };
        _serviceMock.Setup(s => s.CreateAsync(1, 10, request))
            .ReturnsAsync(new ProspectDetailDto { Prospect = new ProspectSummaryDto { ProspectId = 1 } });

        var result = await _controller.Create(request);

        result.Should().BeOfType<CreatedAtActionResult>();
    }

    [Fact]
    public async Task Create_CallsServiceWithCorrectUserIdAndOrgId()
    {
        SetAuthenticatedUser(userId: 3, orgId: 20);
        var request = new CreateProspectRequest { NoticeId = "NOTICE-002" };
        _serviceMock.Setup(s => s.CreateAsync(3, 20, request))
            .ReturnsAsync(new ProspectDetailDto { Prospect = new ProspectSummaryDto { ProspectId = 1 } });

        await _controller.Create(request);

        _serviceMock.Verify(s => s.CreateAsync(3, 20, request), Times.Once);
    }

    [Fact]
    public async Task Create_InvalidOperation_Returns400()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        var request = new CreateProspectRequest { NoticeId = "NOTICE-DUP" };
        _serviceMock.Setup(s => s.CreateAsync(1, 10, request))
            .ThrowsAsync(new InvalidOperationException("Prospect already exists for this opportunity"));

        var result = await _controller.Create(request);

        var statusResult = result as ObjectResult;
        statusResult!.StatusCode.Should().Be(400);
    }

    // --- UpdateStatus (org-scoped) ---

    [Fact]
    public async Task UpdateStatus_NoUser_ReturnsUnauthorized()
    {
        var request = new UpdateProspectStatusRequest();

        var result = await _controller.UpdateStatus(1, request);

        result.Should().BeOfType<UnauthorizedResult>();
    }

    [Fact]
    public async Task UpdateStatus_ValidRequest_ReturnsOk()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        var request = new UpdateProspectStatusRequest();
        _serviceMock.Setup(s => s.UpdateStatusAsync(10, 5, 1, request))
            .ReturnsAsync(new ProspectDetailDto());

        var result = await _controller.UpdateStatus(5, request);

        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task UpdateStatus_ProspectNotFound_Returns404()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        var request = new UpdateProspectStatusRequest();
        _serviceMock.Setup(s => s.UpdateStatusAsync(10, 999, 1, request))
            .ThrowsAsync(new KeyNotFoundException("Prospect not found"));

        var result = await _controller.UpdateStatus(999, request);

        var statusResult = result as ObjectResult;
        statusResult!.StatusCode.Should().Be(404);
    }

    [Fact]
    public async Task UpdateStatus_InvalidTransition_Returns400()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        var request = new UpdateProspectStatusRequest();
        _serviceMock.Setup(s => s.UpdateStatusAsync(10, 5, 1, request))
            .ThrowsAsync(new InvalidOperationException("Invalid status transition"));

        var result = await _controller.UpdateStatus(5, request);

        var statusResult = result as ObjectResult;
        statusResult!.StatusCode.Should().Be(400);
    }

    // --- Reassign (org-scoped) ---

    [Fact]
    public async Task Reassign_NoUser_ReturnsUnauthorized()
    {
        var request = new ReassignProspectRequest();

        var result = await _controller.Reassign(1, request);

        result.Should().BeOfType<UnauthorizedResult>();
    }

    [Fact]
    public async Task Reassign_ValidRequest_ReturnsOk()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        var request = new ReassignProspectRequest();
        _serviceMock.Setup(s => s.ReassignAsync(10, 5, 1, request))
            .ReturnsAsync(new ProspectDetailDto());

        var result = await _controller.Reassign(5, request);

        result.Should().BeOfType<OkObjectResult>();
    }

    // --- RemoveTeamMember (org-scoped) ---

    [Fact]
    public async Task RemoveTeamMember_NoUser_ReturnsUnauthorized()
    {
        var result = await _controller.RemoveTeamMember(1, 2);

        result.Should().BeOfType<UnauthorizedResult>();
    }

    [Fact]
    public async Task RemoveTeamMember_Existing_ReturnsNoContent()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        _serviceMock.Setup(s => s.RemoveTeamMemberAsync(10, 5, 3, 1))
            .ReturnsAsync(true);

        var result = await _controller.RemoveTeamMember(5, 3);

        result.Should().BeOfType<NoContentResult>();
    }

    [Fact]
    public async Task RemoveTeamMember_NotFound_ReturnsNotFound()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        _serviceMock.Setup(s => s.RemoveTeamMemberAsync(10, 5, 999, 1))
            .ReturnsAsync(false);

        var result = await _controller.RemoveTeamMember(5, 999);

        result.Should().BeOfType<NotFoundResult>();
    }

    // --- ResolveOrganizationIdAsync fallback (Gap 11) ---

    [Fact]
    public async Task Search_NoOrgIdClaim_FallsBackToDbLookup_ReturnsOk()
    {
        // Create an in-memory DbContext with a user record
        var dbOptions = new DbContextOptionsBuilder<FedProspectorDbContext>()
            .UseInMemoryDatabase(databaseName: Guid.NewGuid().ToString())
            .Options;
        var dbContext = new FedProspectorDbContext(dbOptions);
        dbContext.AppUsers.Add(new AppUser
        {
            UserId = 5,
            OrganizationId = 77,
            Username = "testuser",
            DisplayName = "Test User"
        });
        dbContext.SaveChanges();

        // Set up DI container with the DbContext
        var services = new ServiceCollection();
        services.AddSingleton(dbContext);
        services.AddSingleton<FedProspectorDbContext>(dbContext);
        var serviceProvider = services.BuildServiceProvider();

        // Create user claims WITHOUT org_id claim, but WITH a valid user ID
        var claims = new List<Claim>
        {
            new(JwtRegisteredClaimNames.Sub, "5"),
            new(ClaimTypes.NameIdentifier, "5"),
            new(ClaimTypes.Role, "user"),
            new("is_org_admin", "false")
            // NOTE: no "org_id" claim -- forces DB fallback
        };
        var user = new ClaimsPrincipal(new ClaimsIdentity(claims, "TestAuth"));

        _controller.ControllerContext.HttpContext = new DefaultHttpContext
        {
            User = user,
            RequestServices = serviceProvider
        };

        var request = new ProspectSearchRequest();
        _serviceMock.Setup(s => s.SearchAsync(77, request))
            .ReturnsAsync(new PagedResponse<ProspectListDto>());

        var result = await _controller.Search(request);

        result.Should().BeOfType<OkObjectResult>();
        _serviceMock.Verify(s => s.SearchAsync(77, request), Times.Once);

        dbContext.Dispose();
    }
}
