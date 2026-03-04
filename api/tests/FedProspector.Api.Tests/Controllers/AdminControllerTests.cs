using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using FedProspector.Api.Controllers;
using FedProspector.Core.DTOs.Admin;
using FedProspector.Core.Interfaces;
using FluentAssertions;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Moq;

namespace FedProspector.Api.Tests.Controllers;

public class AdminControllerTests
{
    private readonly Mock<IAdminService> _serviceMock = new();
    private readonly Mock<IOrganizationService> _orgServiceMock = new();
    private readonly AdminController _controller;

    public AdminControllerTests()
    {
        _controller = new AdminController(_serviceMock.Object, _orgServiceMock.Object);
        _controller.ControllerContext = new ControllerContext
        {
            HttpContext = new DefaultHttpContext()
        };
    }

    private static ClaimsPrincipal CreateUser(int userId = 1, string role = "admin", bool isAdmin = true)
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

    private void SetAuthenticatedAdmin(int userId = 1)
    {
        _controller.ControllerContext.HttpContext.User = CreateUser(userId);
    }

    // --- GetEtlStatus ---

    [Fact]
    public async Task GetEtlStatus_ReturnsOk()
    {
        _serviceMock.Setup(s => s.GetEtlStatusAsync())
            .ReturnsAsync(new EtlStatusDto());

        var result = await _controller.GetEtlStatus();

        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task GetEtlStatus_CallsService()
    {
        _serviceMock.Setup(s => s.GetEtlStatusAsync())
            .ReturnsAsync(new EtlStatusDto());

        await _controller.GetEtlStatus();

        _serviceMock.Verify(s => s.GetEtlStatusAsync(), Times.Once);
    }

    [Fact]
    public async Task GetEtlStatus_ReturnsServiceResult()
    {
        var expected = new EtlStatusDto { Alerts = ["Test alert"] };
        _serviceMock.Setup(s => s.GetEtlStatusAsync()).ReturnsAsync(expected);

        var result = await _controller.GetEtlStatus() as OkObjectResult;

        result!.Value.Should().Be(expected);
    }

    // --- GetUsers ---

    [Fact]
    public async Task GetUsers_ReturnsOk()
    {
        _serviceMock.Setup(s => s.GetUsersAsync())
            .ReturnsAsync(new List<UserListDto>());

        var result = await _controller.GetUsers();

        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task GetUsers_CallsService()
    {
        _serviceMock.Setup(s => s.GetUsersAsync())
            .ReturnsAsync(new List<UserListDto>());

        await _controller.GetUsers();

        _serviceMock.Verify(s => s.GetUsersAsync(), Times.Once);
    }

    // --- UpdateUser ---

    [Fact]
    public async Task UpdateUser_NoAuthenticatedUser_ReturnsUnauthorized()
    {
        var request = new UpdateUserRequest { IsActive = false };

        var result = await _controller.UpdateUser(5, request);

        result.Should().BeOfType<UnauthorizedResult>();
    }

    [Fact]
    public async Task UpdateUser_ValidRequest_ReturnsOk()
    {
        SetAuthenticatedAdmin(userId: 1);
        var request = new UpdateUserRequest { Role = "admin" };
        _serviceMock.Setup(s => s.UpdateUserAsync(5, request, 1))
            .ReturnsAsync(new UserListDto { UserId = 5, Role = "admin" });

        var result = await _controller.UpdateUser(5, request);

        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task UpdateUser_CallsServiceWithCorrectParameters()
    {
        SetAuthenticatedAdmin(userId: 2);
        var request = new UpdateUserRequest { IsAdmin = true };
        _serviceMock.Setup(s => s.UpdateUserAsync(10, request, 2))
            .ReturnsAsync(new UserListDto());

        await _controller.UpdateUser(10, request);

        _serviceMock.Verify(s => s.UpdateUserAsync(10, request, 2), Times.Once);
    }

    [Fact]
    public async Task UpdateUser_InvalidOperation_ThrowsInvalidOperation()
    {
        SetAuthenticatedAdmin(userId: 1);
        var request = new UpdateUserRequest { IsActive = false };
        _serviceMock.Setup(s => s.UpdateUserAsync(1, request, 1))
            .ThrowsAsync(new InvalidOperationException("Cannot deactivate yourself"));

        var act = () => _controller.UpdateUser(1, request);

        await act.Should().ThrowAsync<InvalidOperationException>();
    }

    [Fact]
    public async Task UpdateUser_UserNotFound_ThrowsKeyNotFound()
    {
        SetAuthenticatedAdmin(userId: 1);
        var request = new UpdateUserRequest { Role = "admin" };
        _serviceMock.Setup(s => s.UpdateUserAsync(999, request, 1))
            .ThrowsAsync(new KeyNotFoundException());

        var act = () => _controller.UpdateUser(999, request);

        await act.Should().ThrowAsync<KeyNotFoundException>();
    }

    // --- ResetPassword ---

    [Fact]
    public async Task ResetPassword_NoAuthenticatedUser_ReturnsUnauthorized()
    {
        var result = await _controller.ResetPassword(5);

        result.Should().BeOfType<UnauthorizedResult>();
    }

    [Fact]
    public async Task ResetPassword_ValidRequest_ReturnsOk()
    {
        SetAuthenticatedAdmin(userId: 1);
        _serviceMock.Setup(s => s.ResetPasswordAsync(5, 1))
            .ReturnsAsync(new ResetPasswordResponse { Message = "Password reset. Credentials sent via email." });

        var result = await _controller.ResetPassword(5);

        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task ResetPassword_CallsServiceWithCorrectParameters()
    {
        SetAuthenticatedAdmin(userId: 3);
        _serviceMock.Setup(s => s.ResetPasswordAsync(7, 3))
            .ReturnsAsync(new ResetPasswordResponse());

        await _controller.ResetPassword(7);

        _serviceMock.Verify(s => s.ResetPasswordAsync(7, 3), Times.Once);
    }

    [Fact]
    public async Task ResetPassword_UserNotFound_ThrowsKeyNotFound()
    {
        SetAuthenticatedAdmin(userId: 1);
        _serviceMock.Setup(s => s.ResetPasswordAsync(999, 1))
            .ThrowsAsync(new KeyNotFoundException());

        var act = () => _controller.ResetPassword(999);

        await act.Should().ThrowAsync<KeyNotFoundException>();
    }
}
