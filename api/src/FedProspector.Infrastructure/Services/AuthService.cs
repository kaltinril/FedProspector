using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Security.Cryptography;
using System.Text;
using FedProspector.Core.DTOs;
using FedProspector.Core.Interfaces;
using FedProspector.Core.Models;
using FedProspector.Core.Options;
using FedProspector.Infrastructure.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using Microsoft.IdentityModel.Tokens;

namespace FedProspector.Infrastructure.Services;

public class AuthService : IAuthService
{
    private const int MaxFailedAttempts = 5;
    private static readonly TimeSpan LockoutDuration = TimeSpan.FromMinutes(30);

    private readonly FedProspectorDbContext _db;
    private readonly JwtOptions _jwtOptions;
    private readonly ILogger<AuthService> _logger;

    public AuthService(
        FedProspectorDbContext db,
        IOptions<JwtOptions> jwtOptions,
        ILogger<AuthService> logger)
    {
        _db = db;
        _jwtOptions = jwtOptions.Value;
        _logger = logger;
    }

    public async Task<AuthResult> LoginAsync(string email, string password)
    {
        var user = await _db.AppUsers
            .FirstOrDefaultAsync(u => u.Email == email);

        if (user is null)
        {
            _logger.LogWarning("Login attempt for unknown email: {Email}", email);
            return new AuthResult { Success = false, Error = "Invalid email or password." };
        }

        // Check if account is active
        if (user.IsActive != "Y")
        {
            _logger.LogWarning("Login attempt for inactive user: {UserId}", user.UserId);
            return new AuthResult { Success = false, Error = "Account is inactive." };
        }

        // Check lockout
        if (user.LockedUntil.HasValue && user.LockedUntil.Value > DateTime.UtcNow)
        {
            _logger.LogWarning("Login attempt for locked user: {UserId}, locked until {LockedUntil}",
                user.UserId, user.LockedUntil.Value);
            return new AuthResult { Success = false, Error = "Account is temporarily locked. Try again later." };
        }

        // Verify password
        if (string.IsNullOrEmpty(user.PasswordHash) || !VerifyPassword(password, user.PasswordHash))
        {
            // Increment failed attempts
            user.FailedLoginAttempts++;

            if (user.FailedLoginAttempts >= MaxFailedAttempts)
            {
                user.LockedUntil = DateTime.UtcNow.Add(LockoutDuration);
                _logger.LogWarning("User {UserId} locked out after {Attempts} failed attempts",
                    user.UserId, user.FailedLoginAttempts);
            }

            user.UpdatedAt = DateTime.UtcNow;
            await _db.SaveChangesAsync();

            return new AuthResult { Success = false, Error = "Invalid email or password." };
        }

        // Successful login — reset failed attempts and lockout
        user.FailedLoginAttempts = 0;
        user.LockedUntil = null;
        user.LastLoginAt = DateTime.UtcNow;
        user.UpdatedAt = DateTime.UtcNow;

        // Generate JWT token
        var expiresAt = DateTime.UtcNow.AddHours(_jwtOptions.ExpirationHours);
        var token = GenerateJwtToken(user, expiresAt);

        // Create session record
        var tokenHash = ComputeSha256Hash(token);
        var session = new AppSession
        {
            UserId = user.UserId,
            TokenHash = tokenHash,
            IssuedAt = DateTime.UtcNow,
            ExpiresAt = expiresAt
        };

        _db.AppSessions.Add(session);
        await _db.SaveChangesAsync();

        _logger.LogInformation("User {UserId} logged in successfully", user.UserId);

        return new AuthResult
        {
            Success = true,
            Token = token,
            UserId = user.UserId,
            UserName = user.DisplayName,
            ExpiresAt = expiresAt
        };
    }

    public async Task<bool> LogoutAsync(int userId, string tokenHash)
    {
        var session = await _db.AppSessions
            .FirstOrDefaultAsync(s => s.UserId == userId
                                      && s.TokenHash == tokenHash
                                      && s.RevokedAt == null);

        if (session is null)
        {
            _logger.LogWarning("Logout failed — no active session found for user {UserId}", userId);
            return false;
        }

        session.RevokedAt = DateTime.UtcNow;
        await _db.SaveChangesAsync();

        _logger.LogInformation("User {UserId} logged out, session {SessionId} revoked",
            userId, session.SessionId);
        return true;
    }

    public async Task<AppUser?> GetUserByIdAsync(int userId)
    {
        return await _db.AppUsers.FindAsync(userId);
    }

    public string HashPassword(string password)
    {
        return BCrypt.Net.BCrypt.EnhancedHashPassword(password);
    }

    public bool VerifyPassword(string password, string hashedPassword)
    {
        try
        {
            return BCrypt.Net.BCrypt.EnhancedVerify(password, hashedPassword);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error verifying password hash");
            return false;
        }
    }

    private string GenerateJwtToken(AppUser user, DateTime expiresAt)
    {
        var key = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(_jwtOptions.SecretKey));
        var credentials = new SigningCredentials(key, SecurityAlgorithms.HmacSha256);

        var role = user.IsAdmin == "Y" ? "admin" : "user";

        var claims = new[]
        {
            new Claim(JwtRegisteredClaimNames.Sub, user.UserId.ToString()),
            new Claim(JwtRegisteredClaimNames.Email, user.Email ?? string.Empty),
            new Claim(JwtRegisteredClaimNames.Name, user.DisplayName),
            new Claim(ClaimTypes.Role, role),
            new Claim(JwtRegisteredClaimNames.Jti, Guid.NewGuid().ToString())
        };

        var token = new JwtSecurityToken(
            issuer: _jwtOptions.Issuer,
            audience: _jwtOptions.Audience,
            claims: claims,
            expires: expiresAt,
            signingCredentials: credentials);

        return new JwtSecurityTokenHandler().WriteToken(token);
    }

    private static string ComputeSha256Hash(string input)
    {
        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes(input));
        return Convert.ToHexStringLower(bytes);
    }
}
