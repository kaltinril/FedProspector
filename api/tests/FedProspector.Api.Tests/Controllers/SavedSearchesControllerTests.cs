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

    private static ClaimsPrincipal CreateUser(int userId = 1, string role = "user", bool isAdmin = false)
    {
        var claims = new List<Claim>
        {
            new(JwtRegisteredClaimNames.Sub, userId.ToString()),
            new(ClaimTypes.NameIdentifier, userId.ToString()),
            new(ClaimTypes.Role, role),
            new("is_admin", isAdmin.ToString().ToLower())
        };
        return new ClaimsPrincipal(new ClaimsIdentity(claims, "TestAuth"));
    }

    private void SetAuthenticatedUser(int userId = 1)
    {
        _controller.ControllerContext.HttpContext.User = CreateUser(userId);
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
        SetAuthenticatedUser(userId: 1);
        var request = new CreateSavedSearchRequest { SearchName = "My Search" };
        _serviceMock.Setup(s => s.CreateAsync(1, request))
            .ReturnsAsync(new SavedSearchDto { SearchId = 10 });

        var result = await _controller.Create(request);

        result.Should().BeOfType<CreatedAtActionResult>();
    }

    [Fact]
    public async Task Create_CallsServiceWithCorrectParameters()
    {
        SetAuthenticatedUser(userId: 3);
        var request = new CreateSavedSearchRequest { SearchName = "Test Search" };
        _serviceMock.Setup(s => s.CreateAsync(3, request))
            .ReturnsAsync(new SavedSearchDto());

        await _controller.Create(request);

        _serviceMock.Verify(s => s.CreateAsync(3, request), Times.Once);
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
}
