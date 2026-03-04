using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Security.Cryptography;
using System.Text;
using FedProspector.Api.Middleware;
using FedProspector.Core.DTOs;
using FedProspector.Core.Interfaces;
using FedProspector.Infrastructure.Services;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.RateLimiting;

namespace FedProspector.Api.Controllers;

[Route("api/v1/auth")]
[EnableRateLimiting("auth")]
public class AuthController : ApiControllerBase
{
    private readonly IAuthService _authService;
    private readonly ILogger<AuthController> _logger;

    public AuthController(IAuthService authService, ILogger<AuthController> logger)
    {
        _authService = authService;
        _logger = logger;
    }

    /// <summary>
    /// Authenticate a user and return a JWT token.
    /// Sets httpOnly cookies for browser clients.
    /// </summary>
    [HttpPost("login")]
    [AllowAnonymous]
    [EnableRateLimiting("login_global")]
    public async Task<IActionResult> Login([FromBody] LoginRequest request)
    {
        if (string.IsNullOrWhiteSpace(request.Email) || string.IsNullOrWhiteSpace(request.Password))
        {
            return BadRequest(new AuthResult { Success = false, Error = "Email and password are required." });
        }

        var result = await _authService.LoginAsync(request.Email, request.Password);

        if (!result.Success)
        {
            return Unauthorized(result);
        }

        // Set httpOnly cookies for browser clients
        SetAuthCookies(result);

        return Ok(new { result.UserId, result.UserName, result.ExpiresAt });
    }

    /// <summary>
    /// Revoke the current session token (log out).
    /// Clears auth cookies.
    /// </summary>
    [HttpPost("logout")]
    [Authorize]
    public async Task<IActionResult> Logout()
    {
        var userIdClaim = User.FindFirst(JwtRegisteredClaimNames.Sub)
                          ?? User.FindFirst(ClaimTypes.NameIdentifier);

        if (userIdClaim is null || !int.TryParse(userIdClaim.Value, out var userId))
        {
            return Unauthorized(new { error = "Invalid token." });
        }

        // Extract the raw token from cookie or Authorization header
        var rawToken = ExtractAccessToken();
        if (string.IsNullOrEmpty(rawToken))
        {
            return Unauthorized(new { error = "Missing token." });
        }

        var tokenHash = ComputeSha256Hash(rawToken);

        // Always clear cookies first — client is logged out regardless of DB state
        ClearAuthCookies();

        // Fire-and-forget if session not found; session absence is not a client error
        await _authService.LogoutAsync(userId, tokenHash);

        return Ok(new { message = "Logged out successfully." });
    }

    /// <summary>
    /// Register a new user account using an invite code.
    /// </summary>
    [HttpPost("register")]
    [AllowAnonymous]
    public async Task<IActionResult> Register([FromBody] RegisterRequest request)
    {
        // Rate limit: 3 attempts per minute per IP
        var ipAddress = HttpContext.Connection.RemoteIpAddress?.ToString();
        if (!AuthService.CheckRegistrationRateLimit(ipAddress))
        {
            return StatusCode(429, new { error = "Too many registration attempts. Please try again later." });
        }

        var result = await _authService.RegisterAsync(request);

        if (!result.Success)
        {
            return BadRequest(new { error = result.Error });
        }

        // Set httpOnly cookies for browser clients
        SetAuthCookies(result);

        return Ok(new { result.UserId, result.UserName, result.ExpiresAt });
    }

    /// <summary>
    /// Refresh access token using refresh token cookie.
    /// </summary>
    [HttpPost("refresh")]
    [AllowAnonymous]
    public async Task<IActionResult> Refresh()
    {
        // Read refresh_token from httpOnly cookie
        var refreshToken = Request.Cookies["refresh_token"];
        if (string.IsNullOrEmpty(refreshToken))
        {
            return Unauthorized(new { error = "No refresh token provided." });
        }

        var refreshTokenHash = ComputeSha256Hash(refreshToken);
        var result = await _authService.RefreshTokenAsync(refreshTokenHash);

        if (!result.Success)
        {
            // Clear cookies on failure
            ClearAuthCookies();
            return Unauthorized(new { error = result.Error });
        }

        // Set new cookies
        SetAuthCookies(result);

        return Ok(new { result.UserId, result.UserName, result.ExpiresAt });
    }

    /// <summary>
    /// Change the current user's password. Revokes all active sessions.
    /// </summary>
    [HttpPost("change-password")]
    [Authorize]
    public async Task<IActionResult> ChangePassword([FromBody] ChangePasswordRequest request)
    {
        var userId = GetCurrentUserId();
        if (userId is null)
        {
            return Unauthorized(new { error = "Invalid token." });
        }

        try
        {
            await _authService.ChangePasswordAsync(userId.Value, request.CurrentPassword, request.NewPassword);
            ClearAuthCookies();
            return Ok(new { message = "Password changed successfully. Please log in again." });
        }
        catch (InvalidOperationException ex)
        {
            return BadRequest(new { message = ex.Message });
        }
        catch (KeyNotFoundException)
        {
            return NotFound(new { message = "User not found." });
        }
    }

    /// <summary>
    /// Get the current user's profile.
    /// </summary>
    [HttpGet("me")]
    [Authorize]
    public async Task<IActionResult> GetProfile()
    {
        var userId = GetCurrentUserId();
        if (userId is null)
        {
            return Unauthorized(new { error = "Invalid token." });
        }

        var profile = await _authService.GetProfileAsync(userId.Value);
        return Ok(profile);
    }

    /// <summary>
    /// Update the current user's profile (display name and/or email).
    /// </summary>
    [HttpPatch("me")]
    [Authorize]
    public async Task<IActionResult> UpdateProfile([FromBody] UpdateProfileRequest request)
    {
        var userId = GetCurrentUserId();
        if (userId is null)
        {
            return Unauthorized(new { error = "Invalid token." });
        }

        var profile = await _authService.UpdateProfileAsync(userId.Value, request);
        return Ok(profile);
    }

    /// <summary>
    /// Set httpOnly cookies for access_token, refresh_token, and XSRF-TOKEN.
    /// </summary>
    private void SetAuthCookies(AuthResult result)
    {
        if (!string.IsNullOrEmpty(result.Token))
        {
            Response.Cookies.Append("access_token", result.Token, new CookieOptions
            {
                HttpOnly = true,
                Secure = true,
                SameSite = SameSiteMode.Strict,
                Path = "/api",
                Expires = result.ExpiresAt
            });
        }

        if (!string.IsNullOrEmpty(result.RefreshToken))
        {
            Response.Cookies.Append("refresh_token", result.RefreshToken, new CookieOptions
            {
                HttpOnly = true,
                Secure = true,
                SameSite = SameSiteMode.Strict,
                Path = "/api/v1/auth/refresh",
                Expires = DateTimeOffset.UtcNow.AddDays(7)
            });
        }

        // Set non-httpOnly CSRF token for double-submit pattern
        var csrfToken = CsrfMiddleware.GenerateCsrfToken();
        Response.Cookies.Append("XSRF-TOKEN", csrfToken, new CookieOptions
        {
            HttpOnly = false,
            Secure = true,
            SameSite = SameSiteMode.Strict,
            Path = "/api",
            Expires = result.ExpiresAt
        });
    }

    /// <summary>
    /// Clear all auth cookies on logout or session invalidation.
    /// </summary>
    private void ClearAuthCookies()
    {
        Response.Cookies.Append("access_token", string.Empty, new CookieOptions
        {
            HttpOnly = true,
            Secure = true,
            SameSite = SameSiteMode.Strict,
            Path = "/api",
            MaxAge = TimeSpan.Zero
        });

        Response.Cookies.Append("refresh_token", string.Empty, new CookieOptions
        {
            HttpOnly = true,
            Secure = true,
            SameSite = SameSiteMode.Strict,
            Path = "/api/v1/auth/refresh",
            MaxAge = TimeSpan.Zero
        });

        Response.Cookies.Append("XSRF-TOKEN", string.Empty, new CookieOptions
        {
            HttpOnly = false,
            Secure = true,
            SameSite = SameSiteMode.Strict,
            Path = "/api",
            MaxAge = TimeSpan.Zero
        });
    }

    /// <summary>
    /// Extract the access token from cookie or Authorization header.
    /// </summary>
    private string? ExtractAccessToken()
    {
        // Try Authorization header first
        var authHeader = Request.Headers.Authorization.ToString();
        if (!string.IsNullOrEmpty(authHeader) && authHeader.StartsWith("Bearer ", StringComparison.OrdinalIgnoreCase))
        {
            return authHeader["Bearer ".Length..].Trim();
        }

        // Fall back to cookie
        return Request.Cookies["access_token"];
    }

    private static string ComputeSha256Hash(string input)
    {
        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes(input));
        return Convert.ToHexStringLower(bytes);
    }
}
