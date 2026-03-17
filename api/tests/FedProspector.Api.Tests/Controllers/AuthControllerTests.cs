using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using FedProspector.Api.Controllers;
using FedProspector.Core.DTOs;
using FedProspector.Core.Interfaces;
using FluentAssertions;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Hosting;
using Microsoft.Extensions.Logging;
using Moq;

namespace FedProspector.Api.Tests.Controllers;

public class AuthControllerTests
{
    private readonly Mock<IAuthService> _authServiceMock = new();
    private readonly Mock<ILogger<AuthController>> _loggerMock = new();
    private readonly Mock<IWebHostEnvironment> _environmentMock = new();
    private readonly AuthController _controller;

    public AuthControllerTests()
    {
        _environmentMock.Setup(e => e.EnvironmentName).Returns("Development");
        _controller = new AuthController(_authServiceMock.Object, _loggerMock.Object, _environmentMock.Object);
        _controller.ControllerContext = new ControllerContext
        {
            HttpContext = new DefaultHttpContext()
        };
    }

    private static ClaimsPrincipal CreateUser(int userId = 1, string role = "user", bool isOrgAdmin = false)
    {
        var claims = new List<Claim>
        {
            new(JwtRegisteredClaimNames.Sub, userId.ToString()),
            new(ClaimTypes.NameIdentifier, userId.ToString()),
            new(ClaimTypes.Role, role),
            new("is_org_admin", isOrgAdmin.ToString().ToLower())
        };
        return new ClaimsPrincipal(new ClaimsIdentity(claims, "TestAuth"));
    }

    private void SetAuthenticatedUser(int userId = 1)
    {
        _controller.ControllerContext.HttpContext.User = CreateUser(userId);
    }

    // --- Login ---

    [Fact]
    public async Task Login_EmptyEmail_ReturnsBadRequest()
    {
        var request = new LoginRequest { Email = "", Password = "pass" };

        var result = await _controller.Login(request);

        result.Should().BeOfType<BadRequestObjectResult>();
    }

    [Fact]
    public async Task Login_EmptyPassword_ReturnsBadRequest()
    {
        var request = new LoginRequest { Email = "test@test.com", Password = "" };

        var result = await _controller.Login(request);

        result.Should().BeOfType<BadRequestObjectResult>();
    }

    [Fact]
    public async Task Login_ValidCredentials_ReturnsOk()
    {
        var request = new LoginRequest { Email = "test@test.com", Password = "password" };
        _authServiceMock.Setup(s => s.LoginAsync("test@test.com", "password"))
            .ReturnsAsync(new AuthResult { Success = true, Token = "jwt-token" });

        var result = await _controller.Login(request);

        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task Login_ValidCredentials_CallsServiceWithCorrectParameters()
    {
        var request = new LoginRequest { Email = "user@test.com", Password = "secret" };
        _authServiceMock.Setup(s => s.LoginAsync("user@test.com", "secret"))
            .ReturnsAsync(new AuthResult { Success = true });

        await _controller.Login(request);

        _authServiceMock.Verify(s => s.LoginAsync("user@test.com", "secret"), Times.Once);
    }

    [Fact]
    public async Task Login_InvalidCredentials_ReturnsUnauthorized()
    {
        var request = new LoginRequest { Email = "test@test.com", Password = "wrong" };
        _authServiceMock.Setup(s => s.LoginAsync("test@test.com", "wrong"))
            .ReturnsAsync(new AuthResult { Success = false, Error = "Invalid credentials" });

        var result = await _controller.Login(request);

        result.Should().BeOfType<UnauthorizedObjectResult>();
    }

    // --- Logout ---

    [Fact]
    public async Task Logout_NoUserClaim_ReturnsOk()
    {
        // No user claims set — logout still succeeds (clears cookies)
        var result = await _controller.Logout();

        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task Logout_NoBearerToken_ReturnsOk()
    {
        SetAuthenticatedUser();

        var result = await _controller.Logout();

        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task Logout_ValidRequest_ReturnsOk()
    {
        SetAuthenticatedUser(userId: 1);
        _controller.ControllerContext.HttpContext.Request.Headers.Authorization = "Bearer test-token";
        _authServiceMock.Setup(s => s.LogoutAsync(1, It.IsAny<string>()))
            .ReturnsAsync(true);

        var result = await _controller.Logout();

        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task Logout_NoActiveSession_ReturnsOk()
    {
        SetAuthenticatedUser(userId: 1);
        _controller.ControllerContext.HttpContext.Request.Headers.Authorization = "Bearer test-token";
        _authServiceMock.Setup(s => s.LogoutAsync(1, It.IsAny<string>()))
            .ReturnsAsync(false);

        var result = await _controller.Logout();

        // Fix 13: Logout always returns Ok — session absence is not a client error
        result.Should().BeOfType<OkObjectResult>();
    }

    // --- Register ---

    [Fact]
    public async Task Register_Success_ReturnsOk()
    {
        var request = new RegisterRequest
        {
            Username = "newuser",
            Email = "new@test.com",
            Password = "pass123",
            DisplayName = "New User"
        };
        _authServiceMock.Setup(s => s.RegisterAsync(request, false))
            .ReturnsAsync(new AuthResult { Success = true });

        var result = await _controller.Register(request);

        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task Register_Failure_ReturnsBadRequest()
    {
        var request = new RegisterRequest { Username = "dupe", Email = "dupe@test.com", Password = "p" };
        _authServiceMock.Setup(s => s.RegisterAsync(request, false))
            .ReturnsAsync(new AuthResult { Success = false, Error = "Email taken" });

        var result = await _controller.Register(request);

        result.Should().BeOfType<BadRequestObjectResult>();
    }

    // --- ChangePassword ---

    [Fact]
    public async Task ChangePassword_NoUser_ReturnsUnauthorized()
    {
        var request = new ChangePasswordRequest { CurrentPassword = "old", NewPassword = "new" };

        var result = await _controller.ChangePassword(request);

        result.Should().BeOfType<UnauthorizedObjectResult>();
    }

    [Fact]
    public async Task ChangePassword_Success_ReturnsOk()
    {
        SetAuthenticatedUser(userId: 5);
        var request = new ChangePasswordRequest { CurrentPassword = "old", NewPassword = "new" };
        _authServiceMock.Setup(s => s.ChangePasswordAsync(5, "old", "new"))
            .Returns(Task.CompletedTask);

        var result = await _controller.ChangePassword(request);

        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task ChangePassword_WrongCurrentPassword_ReturnsBadRequest()
    {
        SetAuthenticatedUser(userId: 5);
        var request = new ChangePasswordRequest { CurrentPassword = "wrong", NewPassword = "new" };
        _authServiceMock.Setup(s => s.ChangePasswordAsync(5, "wrong", "new"))
            .ThrowsAsync(new InvalidOperationException("Current password is incorrect"));

        var result = await _controller.ChangePassword(request);

        // Fix 3: InvalidOperationException is caught and mapped to 400 Bad Request
        result.Should().BeOfType<BadRequestObjectResult>();
    }

    // --- GetProfile ---

    [Fact]
    public async Task GetProfile_NoUser_ReturnsUnauthorized()
    {
        var result = await _controller.GetProfile();

        result.Should().BeOfType<UnauthorizedObjectResult>();
    }

    [Fact]
    public async Task GetProfile_ValidUser_ReturnsOk()
    {
        SetAuthenticatedUser(userId: 3);
        _authServiceMock.Setup(s => s.GetProfileAsync(3))
            .ReturnsAsync(new UserProfileDto { UserId = 3, Username = "testuser" });

        var result = await _controller.GetProfile();

        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task GetProfile_UserNotFound_ReturnsNotFound()
    {
        SetAuthenticatedUser(userId: 999);
        _authServiceMock.Setup(s => s.GetProfileAsync(999))
            .ThrowsAsync(new KeyNotFoundException("User not found"));

        var result = await _controller.GetProfile();

        result.Should().BeOfType<NotFoundObjectResult>();
    }

    // --- UpdateProfile ---

    [Fact]
    public async Task UpdateProfile_NoUser_ReturnsUnauthorized()
    {
        var request = new UpdateProfileRequest { DisplayName = "New Name" };

        var result = await _controller.UpdateProfile(request);

        result.Should().BeOfType<UnauthorizedObjectResult>();
    }

    [Fact]
    public async Task UpdateProfile_ValidUser_ReturnsOk()
    {
        SetAuthenticatedUser(userId: 2);
        var request = new UpdateProfileRequest { DisplayName = "Updated" };
        _authServiceMock.Setup(s => s.UpdateProfileAsync(2, request))
            .ReturnsAsync(new UserProfileDto { UserId = 2, DisplayName = "Updated" });

        var result = await _controller.UpdateProfile(request);

        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task UpdateProfile_InvalidOperation_ReturnsBadRequest()
    {
        SetAuthenticatedUser(userId: 2);
        var request = new UpdateProfileRequest { Email = "taken@test.com" };
        _authServiceMock.Setup(s => s.UpdateProfileAsync(2, request))
            .ThrowsAsync(new InvalidOperationException("Email taken"));

        var result = await _controller.UpdateProfile(request);

        result.Should().BeOfType<BadRequestObjectResult>();
    }

    [Fact]
    public async Task UpdateProfile_UserNotFound_ReturnsNotFound()
    {
        SetAuthenticatedUser(userId: 999);
        var request = new UpdateProfileRequest { DisplayName = "test" };
        _authServiceMock.Setup(s => s.UpdateProfileAsync(999, request))
            .ThrowsAsync(new KeyNotFoundException());

        var result = await _controller.UpdateProfile(request);

        result.Should().BeOfType<NotFoundObjectResult>();
    }
}
