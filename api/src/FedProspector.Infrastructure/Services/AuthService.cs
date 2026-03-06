using System.Collections.Concurrent;
using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using FedProspector.Core.DTOs;
using FedProspector.Core.Interfaces;
using FedProspector.Core.Models;
using FedProspector.Core.Options;
using FedProspector.Infrastructure.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Caching.Memory;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using Microsoft.IdentityModel.Tokens;

namespace FedProspector.Infrastructure.Services;

public class AuthService : IAuthService
{
    private const int MaxFailedAttempts = 5;
    private static readonly TimeSpan LockoutDuration = TimeSpan.FromMinutes(30);

    // Progressive delay: track failed login attempts per email for brute-force mitigation
    private const int ProgressiveDelayThreshold = 3;
    private static readonly TimeSpan ProgressiveDelayWindow = TimeSpan.FromMinutes(10);
    private static readonly TimeSpan ProgressiveDelayDuration = TimeSpan.FromSeconds(2);
    private static readonly ConcurrentDictionary<string, List<DateTime>> _failedLoginTracker = new();

    // Invite code lockout tracking (in-memory, since model doesn't have these fields)
    private const int MaxInviteAttempts = 5;
    private const int MaxInviteTrackingEntries = 10_000;
    private static readonly Regex InviteCodePattern = new(@"^[a-f0-9]{64}$", RegexOptions.Compiled);
    private static readonly ConcurrentDictionary<string, int> _inviteFailedAttempts = new();

    // Registration rate limiting: track attempts per IP
    private const int MaxRegisterAttemptsPerMinute = 3;
    private static readonly ConcurrentDictionary<string, List<DateTime>> _registerAttemptTracker = new();

    // Token lifetimes
    private static readonly TimeSpan AccessTokenLifetime = TimeSpan.FromMinutes(30);
    private static readonly TimeSpan RefreshTokenLifetime = TimeSpan.FromDays(7);

    // Session validation cache TTL
    private static readonly TimeSpan SessionCacheTtl = TimeSpan.FromSeconds(30);

    // In-memory revocation set for immediate session invalidation
    private static readonly ConcurrentDictionary<int, DateTime> _revokedUsers = new();

    private readonly FedProspectorDbContext _db;
    private readonly JwtOptions _jwtOptions;
    private readonly ILogger<AuthService> _logger;
    private readonly IActivityLogService _activityLogService;
    private readonly IMemoryCache _cache;

    public AuthService(
        FedProspectorDbContext db,
        IOptions<JwtOptions> jwtOptions,
        ILogger<AuthService> logger,
        IActivityLogService activityLogService,
        IMemoryCache cache)
    {
        _db = db;
        _jwtOptions = jwtOptions.Value;
        _logger = logger;
        _activityLogService = activityLogService;
        _cache = cache;
    }

    public async Task<AuthResult> LoginAsync(string email, string password)
    {
        // Progressive delay: if this email has 3+ failures in the last 10 minutes, add artificial delay
        var normalizedEmail = email.ToLowerInvariant();
        await ApplyProgressiveDelayAsync(normalizedEmail);

        var user = await _db.AppUsers
            .FirstOrDefaultAsync(u => u.Email == email);

        if (user is null)
        {
            RecordFailedAttempt(normalizedEmail);
            _logger.LogWarning("Login attempt for unknown email: {Email}", email);
            return new AuthResult { Success = false, Error = "Invalid email or password." };
        }

        // Check if account is active (generic message to prevent account enumeration)
        if (user.IsActive != "Y")
        {
            RecordFailedAttempt(normalizedEmail);
            _logger.LogWarning("Login attempt for inactive user: {UserId}", user.UserId);
            return new AuthResult { Success = false, Error = "Invalid email or password." };
        }

        // Check lockout (generic message to prevent account enumeration)
        if (user.LockedUntil.HasValue && user.LockedUntil.Value > DateTime.UtcNow)
        {
            RecordFailedAttempt(normalizedEmail);
            _logger.LogWarning("Login attempt for locked user: {UserId}, locked until {LockedUntil}",
                user.UserId, user.LockedUntil.Value);
            return new AuthResult { Success = false, Error = "Invalid email or password." };
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

            await _activityLogService.LogAsync(null, "LOGIN_FAILED", "USER", null, new { Email = email });

            RecordFailedAttempt(normalizedEmail);
            return new AuthResult { Success = false, Error = "Invalid email or password." };
        }

        // Successful login -- reset failed attempts and lockout
        ClearFailedAttempts(normalizedEmail);
        user.FailedLoginAttempts = 0;
        user.LockedUntil = null;
        user.LastLoginAt = DateTime.UtcNow;
        user.UpdatedAt = DateTime.UtcNow;

        // Generate access token (30 min)
        var accessExpiresAt = DateTime.UtcNow.Add(AccessTokenLifetime);
        var accessToken = GenerateJwtToken(user, accessExpiresAt);

        // Generate refresh token (7 days)
        var refreshToken = GenerateRefreshToken();
        var refreshExpiresAt = DateTime.UtcNow.Add(RefreshTokenLifetime);

        // Create session record with access token hash
        var accessTokenHash = ComputeSha256Hash(accessToken);
        var refreshTokenHash = ComputeSha256Hash(refreshToken);
        var session = new AppSession
        {
            UserId = user.UserId,
            TokenHash = accessTokenHash,
            IssuedAt = DateTime.UtcNow,
            ExpiresAt = accessExpiresAt,
            RefreshTokenHash = refreshTokenHash
        };

        _db.AppSessions.Add(session);
        await _db.SaveChangesAsync();

        await _activityLogService.LogAsync(user.UserId, "LOGIN_SUCCESS", "USER", user.UserId.ToString());

        _logger.LogInformation("User {UserId} logged in successfully", user.UserId);

        return new AuthResult
        {
            Success = true,
            Token = accessToken,
            RefreshToken = refreshToken,
            UserId = user.UserId,
            UserName = user.DisplayName,
            ExpiresAt = accessExpiresAt
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
            _logger.LogWarning("Logout failed -- no active session found for user {UserId}", userId);
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

    public async Task<AuthResult> RegisterAsync(RegisterRequest request, bool isAdminRegistration = false)
    {
        // Invite-only registration (unless admin registration)
        int organizationId = 1; // Default org for admin registrations
        string orgRole = "member";

        if (!isAdminRegistration)
        {
            if (string.IsNullOrWhiteSpace(request.InviteCode))
            {
                return new AuthResult { Success = false, Error = "Invite code is required." };
            }

            // Validate invite code format before tracking to prevent dictionary abuse
            if (!InviteCodePattern.IsMatch(request.InviteCode))
            {
                return new AuthResult { Success = false, Error = "Invalid or expired invite code." };
            }

            // Check invite code lockout
            if (_inviteFailedAttempts.TryGetValue(request.InviteCode, out var failCount) && failCount >= MaxInviteAttempts)
            {
                _logger.LogWarning("Invite code locked after {Attempts} failed attempts: {Code}",
                    failCount, request.InviteCode);
                return new AuthResult { Success = false, Error = "This invite code has been locked." };
            }

            // Validate invite code
            var invite = await _db.OrganizationInvites
                .FirstOrDefaultAsync(i => i.InviteCode == request.InviteCode);

            if (invite is null || invite.AcceptedAt.HasValue || invite.ExpiresAt < DateTime.UtcNow)
            {
                // Track failed attempt (evict if dictionary is too large)
                TrackInviteFailedAttempt(request.InviteCode);
                return new AuthResult { Success = false, Error = "Invalid or expired invite code." };
            }

            // Check that the invite email matches (case-insensitive)
            if (!string.Equals(invite.Email, request.Email, StringComparison.OrdinalIgnoreCase))
            {
                TrackInviteFailedAttempt(request.InviteCode);
                return new AuthResult { Success = false, Error = "Email does not match the invitation." };
            }

            organizationId = invite.OrganizationId;
            orgRole = invite.OrgRole;

            // Mark invite as accepted
            invite.AcceptedAt = DateTime.UtcNow;
        }

        // Check username uniqueness (case-insensitive)
        var usernameExists = await _db.AppUsers
            .AnyAsync(u => u.Username.ToLower() == request.Username.ToLower());

        if (usernameExists)
        {
            return new AuthResult { Success = false, Error = "Username already taken" };
        }

        // Check email uniqueness (case-insensitive)
        var emailExists = await _db.AppUsers
            .AnyAsync(u => u.Email != null && u.Email.ToLower() == request.Email.ToLower());

        if (emailExists)
        {
            return new AuthResult { Success = false, Error = "Email already registered" };
        }

        var user = new AppUser
        {
            OrganizationId = organizationId,
            Username = request.Username,
            DisplayName = request.DisplayName,
            Email = request.Email,
            PasswordHash = HashPassword(request.Password),
            Role = "USER",
            OrgRole = orgRole,
            IsActive = "Y",
            IsAdmin = isAdminRegistration ? "Y" : "N",
            MfaEnabled = "N",
            FailedLoginAttempts = 0,
            CreatedAt = DateTime.UtcNow
        };

        _db.AppUsers.Add(user);
        await _db.SaveChangesAsync();

        // Generate access token (30 min) and refresh token (7 days)
        var accessExpiresAt = DateTime.UtcNow.Add(AccessTokenLifetime);
        var accessToken = GenerateJwtToken(user, accessExpiresAt);
        var refreshToken = GenerateRefreshToken();
        var refreshExpiresAt = DateTime.UtcNow.Add(RefreshTokenLifetime);
        var accessTokenHash = ComputeSha256Hash(accessToken);
        var refreshTokenHash = ComputeSha256Hash(refreshToken);

        var session = new AppSession
        {
            UserId = user.UserId,
            TokenHash = accessTokenHash,
            IssuedAt = DateTime.UtcNow,
            ExpiresAt = accessExpiresAt,
            RefreshTokenHash = refreshTokenHash
        };

        _db.AppSessions.Add(session);
        await _db.SaveChangesAsync();

        await _activityLogService.LogAsync(user.UserId, "REGISTER", "USER", user.UserId.ToString());

        _logger.LogInformation("User {UserId} registered successfully with username {Username}",
            user.UserId, user.Username);

        return new AuthResult
        {
            Success = true,
            Token = accessToken,
            RefreshToken = refreshToken,
            UserId = user.UserId,
            UserName = user.DisplayName,
            ExpiresAt = accessExpiresAt
        };
    }

    public async Task ChangePasswordAsync(int userId, string currentPassword, string newPassword)
    {
        var user = await _db.AppUsers.FindAsync(userId);

        if (user is null)
        {
            throw new KeyNotFoundException($"User {userId} not found.");
        }

        if (string.IsNullOrEmpty(user.PasswordHash) || !VerifyPassword(currentPassword, user.PasswordHash))
        {
            throw new InvalidOperationException("Current password is incorrect");
        }

        if (VerifyPassword(newPassword, user.PasswordHash))
        {
            throw new InvalidOperationException("New password must be different from current password.");
        }

        user.PasswordHash = HashPassword(newPassword);
        user.ForcePasswordChange = "N";
        user.UpdatedAt = DateTime.UtcNow;

        // Revoke all active sessions
        var activeSessions = await _db.AppSessions
            .Where(s => s.UserId == userId && s.RevokedAt == null)
            .ToListAsync();

        foreach (var session in activeSessions)
        {
            session.RevokedAt = DateTime.UtcNow;
            session.RefreshTokenHash = null;
        }

        await _db.SaveChangesAsync();

        // Immediately revoke in-memory cache so all requests fail instantly
        RevokeSessionInMemory(userId);

        await _activityLogService.LogAsync(userId, "CHANGE_PASSWORD", "USER", userId.ToString());

        _logger.LogInformation("User {UserId} changed password, {SessionCount} sessions revoked",
            userId, activeSessions.Count);
    }

    public async Task<UserProfileDto> GetProfileAsync(int userId)
    {
        var user = await _db.AppUsers
            .AsNoTracking()
            .FirstOrDefaultAsync(u => u.UserId == userId);

        if (user is null)
        {
            throw new KeyNotFoundException($"User {userId} not found.");
        }

        return MapToProfileDto(user);
    }

    public async Task<UserProfileDto> UpdateProfileAsync(int userId, UpdateProfileRequest request)
    {
        var user = await _db.AppUsers.FindAsync(userId);

        if (user is null)
        {
            throw new KeyNotFoundException($"User {userId} not found.");
        }

        if (request.DisplayName is not null)
        {
            user.DisplayName = request.DisplayName;
        }

        if (request.Email is not null)
        {
            // Verify current password before allowing email change
            if (string.IsNullOrEmpty(request.CurrentPassword) ||
                string.IsNullOrEmpty(user.PasswordHash) ||
                !VerifyPassword(request.CurrentPassword, user.PasswordHash))
            {
                throw new InvalidOperationException("Current password is required to change email.");
            }

            // Check email uniqueness (exclude current user)
            var emailExists = await _db.AppUsers
                .AnyAsync(u => u.UserId != userId && u.Email != null && u.Email.ToLower() == request.Email.ToLower());

            if (emailExists)
            {
                throw new InvalidOperationException("Email already registered");
            }

            user.Email = request.Email;
        }

        user.UpdatedAt = DateTime.UtcNow;
        await _db.SaveChangesAsync();

        _logger.LogInformation("User {UserId} updated profile", userId);

        return MapToProfileDto(user);
    }

    public async Task<AuthResult> RefreshTokenAsync(string refreshTokenHash)
    {
        // Find session by refresh token hash
        var session = await _db.AppSessions
            .Include(s => s.User)
            .FirstOrDefaultAsync(s => s.RefreshTokenHash == refreshTokenHash && s.RevokedAt == null);

        if (session is null)
        {
            // Check if this is a reuse of an already-rotated token (token reuse detection)
            var rotatedSession = await _db.AppSessions
                .FirstOrDefaultAsync(s => s.RefreshTokenHash == refreshTokenHash && s.RevokedAt != null);

            if (rotatedSession != null)
            {
                // Token reuse detected -- revoke ALL sessions for this user
                _logger.LogWarning("Refresh token reuse detected for user {UserId}. Revoking all sessions.",
                    rotatedSession.UserId);

                await RevokeAllUserSessionsAsync(rotatedSession.UserId, "refresh_token_reuse");
                return new AuthResult { Success = false, Error = "Session expired. Please log in again." };
            }

            return new AuthResult { Success = false, Error = "Invalid refresh token." };
        }

        // Check if the session's refresh token has expired (issued_at + 7 days)
        if (session.IssuedAt.Add(RefreshTokenLifetime) < DateTime.UtcNow)
        {
            session.RevokedAt = DateTime.UtcNow;
            await _db.SaveChangesAsync();
            return new AuthResult { Success = false, Error = "Refresh token expired." };
        }

        var user = session.User;
        if (user is null || user.IsActive != "Y")
        {
            return new AuthResult { Success = false, Error = "Account is inactive." };
        }

        // Rotate: invalidate old session and clear its refresh token hash
        session.RevokedAt = DateTime.UtcNow;
        session.RefreshTokenHash = null;

        // Generate new tokens
        var accessExpiresAt = DateTime.UtcNow.Add(AccessTokenLifetime);
        var newAccessToken = GenerateJwtToken(user, accessExpiresAt);
        var newRefreshToken = GenerateRefreshToken();
        var newAccessHash = ComputeSha256Hash(newAccessToken);
        var newRefreshHash = ComputeSha256Hash(newRefreshToken);

        var newSession = new AppSession
        {
            UserId = user.UserId,
            TokenHash = newAccessHash,
            IssuedAt = DateTime.UtcNow,
            ExpiresAt = accessExpiresAt,
            RefreshTokenHash = newRefreshHash
        };

        _db.AppSessions.Add(newSession);
        await _db.SaveChangesAsync();

        _logger.LogInformation("User {UserId} refreshed token, old session {OldSessionId} rotated",
            user.UserId, session.SessionId);

        return new AuthResult
        {
            Success = true,
            Token = newAccessToken,
            RefreshToken = newRefreshToken,
            UserId = user.UserId,
            UserName = user.DisplayName,
            ExpiresAt = accessExpiresAt
        };
    }

    public async Task<bool> ValidateSessionAsync(int userId, string tokenHash)
    {
        // Check in-memory revocation set first (instant revocation for password changes, admin deactivation)
        if (_revokedUsers.TryGetValue(userId, out var revokedAt))
        {
            // Keep revocation entries for 1 hour, then let DB check handle it
            if (revokedAt > DateTime.UtcNow.AddHours(-1))
            {
                return false;
            }
            _revokedUsers.TryRemove(userId, out _);
        }

        // Use memory cache to avoid DB hit on every request
        var cacheKey = $"session:{userId}:{tokenHash}";
        if (_cache.TryGetValue(cacheKey, out bool cachedResult))
        {
            return cachedResult;
        }

        // DB check: session exists and not revoked
        var isValid = await _db.AppSessions
            .AsNoTracking()
            .AnyAsync(s => s.UserId == userId
                        && s.TokenHash == tokenHash
                        && s.RevokedAt == null
                        && s.ExpiresAt > DateTime.UtcNow);

        _cache.Set(cacheKey, isValid, SessionCacheTtl);
        return isValid;
    }

    public void RevokeSessionInMemory(int userId)
    {
        _revokedUsers[userId] = DateTime.UtcNow;
    }

    public async Task RevokeAllUserSessionsAsync(int userId, string reason)
    {
        var activeSessions = await _db.AppSessions
            .Where(s => s.UserId == userId && s.RevokedAt == null)
            .ToListAsync();

        foreach (var session in activeSessions)
        {
            session.RevokedAt = DateTime.UtcNow;
            session.RefreshTokenHash = null;
        }

        await _db.SaveChangesAsync();

        // Add to in-memory revocation set for immediate effect
        RevokeSessionInMemory(userId);

        await _activityLogService.LogAsync(userId, "SESSIONS_REVOKED", "USER", userId.ToString(),
            new { Reason = reason, SessionCount = activeSessions.Count });

        _logger.LogWarning("All {Count} sessions revoked for user {UserId}. Reason: {Reason}",
            activeSessions.Count, userId, reason);
    }

    /// <summary>
    /// Check registration rate limit for an IP address.
    /// Returns true if the request should be allowed.
    /// </summary>
    public static bool CheckRegistrationRateLimit(string? ipAddress)
    {
        if (string.IsNullOrEmpty(ipAddress)) return true;

        var attempts = _registerAttemptTracker.GetOrAdd(ipAddress, _ => new List<DateTime>());
        var cutoff = DateTime.UtcNow.AddMinutes(-1);

        lock (attempts)
        {
            attempts.RemoveAll(t => t <= cutoff);

            if (attempts.Count >= MaxRegisterAttemptsPerMinute)
            {
                return false;
            }

            attempts.Add(DateTime.UtcNow);
            return true;
        }
    }

    private static UserProfileDto MapToProfileDto(AppUser user)
    {
        return new UserProfileDto
        {
            UserId = user.UserId,
            Username = user.Username,
            DisplayName = user.DisplayName,
            Email = user.Email,
            Role = user.Role ?? "USER",
            IsAdmin = user.IsAdmin == "Y",
            LastLoginAt = user.LastLoginAt,
            CreatedAt = user.CreatedAt
        };
    }

    private string GenerateJwtToken(AppUser user, DateTime expiresAt)
    {
        var key = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(_jwtOptions.SecretKey));
        var credentials = new SigningCredentials(key, SecurityAlgorithms.HmacSha256);

        var role = user.IsAdmin == "Y" ? "admin" : "user";

        var claims = new List<Claim>
        {
            new(JwtRegisteredClaimNames.Sub, user.UserId.ToString()),
            new(JwtRegisteredClaimNames.Email, user.Email ?? string.Empty),
            new(JwtRegisteredClaimNames.Name, user.DisplayName),
            new(ClaimTypes.Role, role),
            new("is_system_admin", user.IsSystemAdmin ? "true" : "false"),
            new("force_password_change", user.ForcePasswordChange == "Y" ? "true" : "false"),
            new(JwtRegisteredClaimNames.Jti, Guid.NewGuid().ToString()),
            new("org_id", user.OrganizationId.ToString()),
            new("org_role", user.OrgRole)
        };

        var token = new JwtSecurityToken(
            issuer: _jwtOptions.Issuer,
            audience: _jwtOptions.Audience,
            claims: claims,
            expires: expiresAt,
            signingCredentials: credentials);

        return new JwtSecurityTokenHandler().WriteToken(token);
    }

    private static string GenerateRefreshToken()
    {
        var bytes = RandomNumberGenerator.GetBytes(64);
        return Convert.ToBase64String(bytes);
    }

    private static string ComputeSha256Hash(string input)
    {
        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes(input));
        return Convert.ToHexStringLower(bytes);
    }

    /// <summary>
    /// Apply progressive delay if an email has exceeded the failure threshold within the tracking window.
    /// </summary>
    private static async Task ApplyProgressiveDelayAsync(string normalizedEmail)
    {
        if (_failedLoginTracker.TryGetValue(normalizedEmail, out var attempts))
        {
            var cutoff = DateTime.UtcNow.Subtract(ProgressiveDelayWindow);
            var recentCount = 0;
            lock (attempts)
            {
                recentCount = attempts.Count(t => t > cutoff);
            }

            if (recentCount >= ProgressiveDelayThreshold)
            {
                await Task.Delay(ProgressiveDelayDuration);
            }
        }
    }

    /// <summary>
    /// Record a failed login attempt for progressive delay tracking.
    /// </summary>
    private static void RecordFailedAttempt(string normalizedEmail)
    {
        var attempts = _failedLoginTracker.GetOrAdd(normalizedEmail, _ => new List<DateTime>());
        var cutoff = DateTime.UtcNow.Subtract(ProgressiveDelayWindow);
        lock (attempts)
        {
            // Prune expired entries while adding new one
            attempts.RemoveAll(t => t <= cutoff);
            attempts.Add(DateTime.UtcNow);
        }
    }

    /// <summary>
    /// Clear failed attempt tracking on successful login.
    /// </summary>
    private static void ClearFailedAttempts(string normalizedEmail)
    {
        _failedLoginTracker.TryRemove(normalizedEmail, out _);
    }

    /// <summary>
    /// Track a failed invite code attempt with bounded dictionary size.
    /// </summary>
    private static void TrackInviteFailedAttempt(string inviteCode)
    {
        if (_inviteFailedAttempts.Count >= MaxInviteTrackingEntries)
        {
            _inviteFailedAttempts.Clear();
        }
        _inviteFailedAttempts.AddOrUpdate(inviteCode, 1, (_, count) => count + 1);
    }
}
