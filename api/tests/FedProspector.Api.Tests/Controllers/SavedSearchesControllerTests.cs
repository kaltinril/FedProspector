using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using FedProspector.Api.Controllers;
using FedProspector.Core.DTOs.SavedSearches;
using FedProspector.Core.Interfaces;
using FluentAssertions;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Moq;

namespace FedProspector.Api.Tests.Controllers;

public class SavedSearchesControllerTests
{
    private readonly Mock<ISavedSearchService> _serviceMock = new();
    private readonly SavedSearchesController _controller;

    public SavedSearchesControllerTests()
    {
        _controller = new SavedSearchesController(_serviceMock.Object);
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

    // --- List ---

    [Fact]
    public async Task List_NoUser_ReturnsUnauthorized()
    {
        var result = await _controller.List();

        result.Should().BeOfType<UnauthorizedResult>();
    }

    [Fact]
    public async Task List_AuthenticatedUser_ReturnsOk()
    {
        SetAuthenticatedUser(userId: 1);
        _serviceMock.Setup(s => s.ListAsync(1))
            .ReturnsAsync(new List<SavedSearchDto>());

        var result = await _controller.List();

        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task List_AuthenticatedUser_CallsServiceWithCorrectUserId()
    {
        SetAuthenticatedUser(userId: 5);
        _serviceMock.Setup(s => s.ListAsync(5))
            .ReturnsAsync(new List<SavedSearchDto>());

        await _controller.List();

        _serviceMock.Verify(s => s.ListAsync(5), Times.Once);
    }

    // --- Create ---

    [Fact]
    public async Task Create_NoUser_ReturnsUnauthorized()
    {
        var request = new CreateSavedSearchRequest { SearchName = "test" };

        var result = await _controller.Create(request);

        result.Should().BeOfType<UnauthorizedResult>();
    }

    [Fact]
    public async Task Create_AuthenticatedUser_ReturnsCreatedAtAction()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        var request = new CreateSavedSearchRequest { SearchName = "My Search" };
        _serviceMock.Setup(s => s.CreateAsync(1, 10, request))
            .ReturnsAsync(new SavedSearchDto { SearchId = 10 });

        var result = await _controller.Create(request);

        result.Should().BeOfType<CreatedAtActionResult>();
    }

    [Fact]
    public async Task Create_CallsServiceWithCorrectParameters()
    {
        SetAuthenticatedUser(userId: 3, orgId: 20);
        var request = new CreateSavedSearchRequest { SearchName = "Test Search" };
        _serviceMock.Setup(s => s.CreateAsync(3, 20, request))
            .ReturnsAsync(new SavedSearchDto());

        await _controller.Create(request);

        _serviceMock.Verify(s => s.CreateAsync(3, 20, request), Times.Once);
    }

    // --- Run ---

    [Fact]
    public async Task Run_NoUser_ReturnsUnauthorized()
    {
        var result = await _controller.Run(1);

        result.Should().BeOfType<UnauthorizedResult>();
    }

    [Fact]
    public async Task Run_ExistingSearch_ReturnsOk()
    {
        SetAuthenticatedUser(userId: 1);
        _serviceMock.Setup(s => s.RunAsync(1, 10))
            .ReturnsAsync(new SavedSearchRunResultDto());

        var result = await _controller.Run(10);

        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task Run_NonExistingSearch_ReturnsNotFound()
    {
        SetAuthenticatedUser(userId: 1);
        _serviceMock.Setup(s => s.RunAsync(1, 999))
            .ReturnsAsync((SavedSearchRunResultDto?)null);

        var result = await _controller.Run(999);

        result.Should().BeOfType<NotFoundResult>();
    }

    [Fact]
    public async Task Run_CallsServiceWithCorrectParameters()
    {
        SetAuthenticatedUser(userId: 2);
        _serviceMock.Setup(s => s.RunAsync(2, 5))
            .ReturnsAsync(new SavedSearchRunResultDto());

        await _controller.Run(5);

        _serviceMock.Verify(s => s.RunAsync(2, 5), Times.Once);
    }

    // --- Delete ---

    [Fact]
    public async Task Delete_NoUser_ReturnsUnauthorized()
    {
        var result = await _controller.Delete(1);

        result.Should().BeOfType<UnauthorizedResult>();
    }

    [Fact]
    public async Task Delete_ExistingSearch_ReturnsNoContent()
    {
        SetAuthenticatedUser(userId: 1);
        _serviceMock.Setup(s => s.DeleteAsync(1, 10))
            .ReturnsAsync(true);

        var result = await _controller.Delete(10);

        result.Should().BeOfType<NoContentResult>();
    }

    [Fact]
    public async Task Delete_NonExistingSearch_ReturnsNotFound()
    {
        SetAuthenticatedUser(userId: 1);
        _serviceMock.Setup(s => s.DeleteAsync(1, 999))
            .ReturnsAsync(false);

        var result = await _controller.Delete(999);

        result.Should().BeOfType<NotFoundResult>();
    }

    [Fact]
    public async Task Delete_CallsServiceWithCorrectParameters()
    {
        SetAuthenticatedUser(userId: 4);
        _serviceMock.Setup(s => s.DeleteAsync(4, 8))
            .ReturnsAsync(true);

        await _controller.Delete(8);

        _serviceMock.Verify(s => s.DeleteAsync(4, 8), Times.Once);
    }

    // --- Update ---

    [Fact]
    public async Task Update_NoUser_ReturnsUnauthorized()
    {
        var request = new UpdateSavedSearchRequest { Name = "Updated Name" };

        var result = await _controller.Update(1, request);

        result.Should().BeOfType<UnauthorizedResult>();
    }

    [Fact]
    public async Task Update_ExistingSearch_ReturnsOk()
    {
        SetAuthenticatedUser(userId: 1);
        var request = new UpdateSavedSearchRequest { Name = "Updated Name" };
        _serviceMock.Setup(s => s.UpdateAsync(1, 10, request))
            .ReturnsAsync(new SavedSearchDto { SearchId = 10, SearchName = "Updated Name" });

        var result = await _controller.Update(10, request);

        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task Update_NonExistingSearch_ReturnsNotFound()
    {
        SetAuthenticatedUser(userId: 1);
        var request = new UpdateSavedSearchRequest { Name = "Test" };
        _serviceMock.Setup(s => s.UpdateAsync(1, 999, request))
            .ReturnsAsync((SavedSearchDto?)null);

        var result = await _controller.Update(999, request);

        result.Should().BeOfType<NotFoundResult>();
    }

    [Fact]
    public async Task Update_CallsServiceWithCorrectParameters()
    {
        SetAuthenticatedUser(userId: 3);
        var request = new UpdateSavedSearchRequest { Description = "New desc", NotificationsEnabled = true };
        _serviceMock.Setup(s => s.UpdateAsync(3, 5, request))
            .ReturnsAsync(new SavedSearchDto());

        await _controller.Update(5, request);

        _serviceMock.Verify(s => s.UpdateAsync(3, 5, request), Times.Once);
    }

    [Fact]
    public async Task Update_ReturnsServiceResult()
    {
        SetAuthenticatedUser(userId: 1);
        var request = new UpdateSavedSearchRequest { Name = "New Name" };
        var expected = new SavedSearchDto { SearchId = 10, SearchName = "New Name" };
        _serviceMock.Setup(s => s.UpdateAsync(1, 10, request)).ReturnsAsync(expected);

        var result = await _controller.Update(10, request) as OkObjectResult;

        result!.Value.Should().Be(expected);
    }
}
