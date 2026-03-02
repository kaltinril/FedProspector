using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using FedProspector.Api.Controllers;
using FedProspector.Core.DTOs;
using FedProspector.Core.DTOs.Notifications;
using FedProspector.Core.Interfaces;
using FluentAssertions;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Moq;

namespace FedProspector.Api.Tests.Controllers;

public class NotificationsControllerTests
{
    private readonly Mock<INotificationService> _serviceMock = new();
    private readonly NotificationsController _controller;

    public NotificationsControllerTests()
    {
        _controller = new NotificationsController(_serviceMock.Object);
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
        var request = new NotificationListRequest();

        var result = await _controller.List(request);

        result.Should().BeOfType<UnauthorizedResult>();
    }

    [Fact]
    public async Task List_AuthenticatedUser_ReturnsOk()
    {
        SetAuthenticatedUser(userId: 1);
        var request = new NotificationListRequest();
        _serviceMock.Setup(s => s.GetNotificationsAsync(1, request))
            .ReturnsAsync(new NotificationListResponse());

        var result = await _controller.List(request);

        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task List_CallsServiceWithCorrectParameters()
    {
        SetAuthenticatedUser(userId: 3);
        var request = new NotificationListRequest { UnreadOnly = true };
        _serviceMock.Setup(s => s.GetNotificationsAsync(3, request))
            .ReturnsAsync(new NotificationListResponse());

        await _controller.List(request);

        _serviceMock.Verify(s => s.GetNotificationsAsync(3, request), Times.Once);
    }

    // --- MarkAsRead ---

    [Fact]
    public async Task MarkAsRead_NoUser_ReturnsUnauthorized()
    {
        var result = await _controller.MarkAsRead(1);

        result.Should().BeOfType<UnauthorizedResult>();
    }

    [Fact]
    public async Task MarkAsRead_ValidRequest_ReturnsOk()
    {
        SetAuthenticatedUser(userId: 1);
        _serviceMock.Setup(s => s.MarkAsReadAsync(1, 5))
            .Returns(Task.CompletedTask);

        var result = await _controller.MarkAsRead(5);

        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task MarkAsRead_CallsServiceWithCorrectParameters()
    {
        SetAuthenticatedUser(userId: 2);
        _serviceMock.Setup(s => s.MarkAsReadAsync(2, 10))
            .Returns(Task.CompletedTask);

        await _controller.MarkAsRead(10);

        _serviceMock.Verify(s => s.MarkAsReadAsync(2, 10), Times.Once);
    }

    [Fact]
    public async Task MarkAsRead_NotificationNotFound_Returns404()
    {
        SetAuthenticatedUser(userId: 1);
        _serviceMock.Setup(s => s.MarkAsReadAsync(1, 999))
            .ThrowsAsync(new KeyNotFoundException("Notification not found"));

        var result = await _controller.MarkAsRead(999);

        var statusResult = result as ObjectResult;
        statusResult!.StatusCode.Should().Be(404);
    }

    // --- MarkAllAsRead ---

    [Fact]
    public async Task MarkAllAsRead_NoUser_ReturnsUnauthorized()
    {
        var result = await _controller.MarkAllAsRead();

        result.Should().BeOfType<UnauthorizedResult>();
    }

    [Fact]
    public async Task MarkAllAsRead_ValidRequest_ReturnsOk()
    {
        SetAuthenticatedUser(userId: 1);
        _serviceMock.Setup(s => s.MarkAllAsReadAsync(1))
            .Returns(Task.CompletedTask);

        var result = await _controller.MarkAllAsRead();

        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task MarkAllAsRead_CallsServiceWithCorrectUserId()
    {
        SetAuthenticatedUser(userId: 7);
        _serviceMock.Setup(s => s.MarkAllAsReadAsync(7))
            .Returns(Task.CompletedTask);

        await _controller.MarkAllAsRead();

        _serviceMock.Verify(s => s.MarkAllAsReadAsync(7), Times.Once);
    }
}
