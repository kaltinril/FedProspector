using FedProspector.Core.DTOs;
using FedProspector.Core.Interfaces;
using FedProspector.Core.Models;
using FedProspector.Core.Options;
using FedProspector.Infrastructure.Data;
using FedProspector.Infrastructure.Services;
using FluentAssertions;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Caching.Memory;
using Microsoft.Extensions.Logging.Abstractions;
using Microsoft.Extensions.Options;
using Moq;

namespace FedProspector.Infrastructure.Tests.Services;

public class AuthServiceTests : IDisposable
{
    private readonly FedProspectorDbContext _context;
    private readonly AuthService _service;
    private readonly Mock<IActivityLogService> _activityLogMock;
    private readonly IMemoryCache _cache;

    private const string TestPassword = "Test@1234!";
    private const string TestSecretKey = "ThisIsATestSecretKeyThatIsLongEnoughForHmacSha256Algorithm!";

    public AuthServiceTests()
    {
        var options = new DbContextOptionsBuilder<FedProspectorDbContext>()
            .UseInMemoryDatabase(databaseName: Guid.NewGuid().ToString())
            .Options;

        _context = new FedProspectorDbContext(options);

        var jwtOptions = Options.Create(new JwtOptions
        {
            SecretKey = TestSecretKey,
            Issuer = "TestIssuer",
            Audience = "TestAudience"
        });

        _activityLogMock = new Mock<IActivityLogService>();
        _cache = new MemoryCache(new MemoryCacheOptions());

        _service = new AuthService(
            _context,
            jwtOptions,
            NullLogger<AuthService>.Instance,
            _activityLogMock.Object,
            _cache);
    }

    public void Dispose()
    {
        _cache.Dispose();
        _context.Dispose();
    }

    private AppUser SeedUser(
        int userId = 0,
        string email = "test@example.com",
        string username = "testuser",
        string displayName = "Test User",
        string password = TestPassword,
        string isActive = "Y",
        string isOrgAdmin = "N",
        int organizationId = 1,
        int failedLoginAttempts = 0,
        DateTime? lockedUntil = null)
    {
        var user = new AppUser
        {
            OrganizationId = organizationId,
            Username = username,
            DisplayName = displayName,
            Email = email,
            PasswordHash = _service.HashPassword(password),
            Role = "USER",
            OrgRole = "member",
            IsActive = isActive,
            IsOrgAdmin = isOrgAdmin,
            MfaEnabled = "N",
            ForcePasswordChange = "N",
            FailedLoginAttempts = failedLoginAttempts,
            LockedUntil = lockedUntil,
            CreatedAt = DateTime.UtcNow
        };

        // Allow explicit userId for tests that need to avoid static state collisions
        if (userId > 0)
            user.UserId = userId;

        _context.AppUsers.Add(user);
        _context.SaveChanges();

        return user;
    }

    private void SeedOrganization(int orgId = 1, string name = "Test Org")
    {
        _context.Organizations.Add(new Organization
        {
            OrganizationId = orgId,
            Name = name,
            Slug = name.ToLower().Replace(" ", "-"),
            IsActive = "Y",
            CreatedAt = DateTime.UtcNow,
            UpdatedAt = DateTime.UtcNow
        });
        _context.SaveChanges();
    }

    // --- Login Tests ---

    [Fact]
    public async Task LoginAsync_ValidCredentials_ReturnsSuccess()
    {
        SeedUser();

        var result = await _service.LoginAsync("test@example.com", TestPassword);

        result.Success.Should().BeTrue();
        result.Token.Should().NotBeNullOrEmpty();
        result.RefreshToken.Should().NotBeNullOrEmpty();
        result.UserId.Should().NotBeNull();
        result.UserName.Should().Be("Test User");
        result.ExpiresAt.Should().BeAfter(DateTime.UtcNow);
    }

    [Fact]
    public async Task LoginAsync_InvalidPassword_ReturnsFailure()
    {
        SeedUser();

        var result = await _service.LoginAsync("test@example.com", "WrongPassword!");

        result.Success.Should().BeFalse();
        result.Error.Should().Be("Invalid email or password.");
        result.Token.Should().BeNull();
    }

    [Fact]
    public async Task LoginAsync_NonexistentUser_ReturnsFailure()
    {
        var result = await _service.LoginAsync("nobody@example.com", "AnyPassword");

        result.Success.Should().BeFalse();
        result.Error.Should().Be("Invalid email or password.");
    }

    [Fact]
    public async Task LoginAsync_InactiveUser_ReturnsFailure()
    {
        SeedUser(isActive: "N");

        var result = await _service.LoginAsync("test@example.com", TestPassword);

        result.Success.Should().BeFalse();
        result.Error.Should().Be("Invalid email or password.");
    }

    [Fact]
    public async Task LoginAsync_LockedOut_ReturnsFailure()
    {
        SeedUser(lockedUntil: DateTime.UtcNow.AddMinutes(30));

        var result = await _service.LoginAsync("test@example.com", TestPassword);

        result.Success.Should().BeFalse();
        result.Error.Should().Be("Invalid email or password.");
    }

    [Fact]
    public async Task LoginAsync_IncrementsFailedAttempts_OnWrongPassword()
    {
        var user = SeedUser();

        await _service.LoginAsync("test@example.com", "WrongPassword!");

        var updatedUser = await _context.AppUsers.FindAsync(user.UserId);
        updatedUser!.FailedLoginAttempts.Should().Be(1);
    }

    [Fact]
    public async Task LoginAsync_LocksAccount_After5FailedAttempts()
    {
        var user = SeedUser(failedLoginAttempts: 4);

        await _service.LoginAsync("test@example.com", "WrongPassword!");

        var updatedUser = await _context.AppUsers.FindAsync(user.UserId);
        updatedUser!.FailedLoginAttempts.Should().Be(5);
        updatedUser.LockedUntil.Should().NotBeNull();
        updatedUser.LockedUntil.Should().BeAfter(DateTime.UtcNow);
    }

    [Fact]
    public async Task LoginAsync_ResetsFailedAttempts_OnSuccess()
    {
        var user = SeedUser(failedLoginAttempts: 3);

        var result = await _service.LoginAsync("test@example.com", TestPassword);

        result.Success.Should().BeTrue();
        var updatedUser = await _context.AppUsers.FindAsync(user.UserId);
        updatedUser!.FailedLoginAttempts.Should().Be(0);
        updatedUser.LockedUntil.Should().BeNull();
    }

    [Fact]
    public async Task LoginAsync_CreatesSession()
    {
        SeedUser();

        var result = await _service.LoginAsync("test@example.com", TestPassword);

        result.Success.Should().BeTrue();
        var sessions = await _context.AppSessions.Where(s => s.UserId == result.UserId).ToListAsync();
        sessions.Should().HaveCount(1);
        sessions[0].RevokedAt.Should().BeNull();
        sessions[0].TokenHash.Should().NotBeNullOrEmpty();
    }

    // --- Password Hashing Tests ---

    [Fact]
    public void HashPassword_ReturnsNonEmptyHash()
    {
        var hash = _service.HashPassword("SomePassword123!");

        hash.Should().NotBeNullOrEmpty();
        hash.Should().NotBe("SomePassword123!");
    }

    [Fact]
    public void HashPassword_DifferentInputs_ProduceDifferentHashes()
    {
        var hash1 = _service.HashPassword("Password1!");
        var hash2 = _service.HashPassword("Password2!");

        hash1.Should().NotBe(hash2);
    }

    [Fact]
    public void VerifyPassword_CorrectPassword_ReturnsTrue()
    {
        var hash = _service.HashPassword("MySecret!");

        var result = _service.VerifyPassword("MySecret!", hash);

        result.Should().BeTrue();
    }

    [Fact]
    public void VerifyPassword_WrongPassword_ReturnsFalse()
    {
        var hash = _service.HashPassword("MySecret!");

        var result = _service.VerifyPassword("WrongSecret!", hash);

        result.Should().BeFalse();
    }

    [Fact]
    public void VerifyPassword_InvalidHash_ReturnsFalse()
    {
        var result = _service.VerifyPassword("AnyPassword", "not-a-valid-bcrypt-hash");

        result.Should().BeFalse();
    }

    // --- Register Tests ---

    [Fact]
    public async Task RegisterAsync_AdminRegistration_CreatesUser()
    {
        var request = new RegisterRequest
        {
            Username = "newadmin",
            Email = "admin@example.com",
            Password = "Admin@1234!",
            DisplayName = "New Admin"
        };

        var result = await _service.RegisterAsync(request, isAdminRegistration: true);

        result.Success.Should().BeTrue();
        result.Token.Should().NotBeNullOrEmpty();
        result.RefreshToken.Should().NotBeNullOrEmpty();
        result.UserId.Should().NotBeNull();
        result.UserName.Should().Be("New Admin");

        var user = await _context.AppUsers.FirstOrDefaultAsync(u => u.Username == "newadmin");
        user.Should().NotBeNull();
        user!.Email.Should().Be("admin@example.com");
        user.IsOrgAdmin.Should().Be("Y");
        user.IsActive.Should().Be("Y");
    }

    [Fact]
    public async Task RegisterAsync_DuplicateEmail_Fails()
    {
        SeedUser(email: "taken@example.com");

        var request = new RegisterRequest
        {
            Username = "different",
            Email = "taken@example.com",
            Password = "Password@1!",
            DisplayName = "Another User"
        };

        var result = await _service.RegisterAsync(request, isAdminRegistration: true);

        result.Success.Should().BeFalse();
        result.Error.Should().Contain("Email already registered");
    }

    [Fact]
    public async Task RegisterAsync_DuplicateUsername_Fails()
    {
        SeedUser(username: "takenuser");

        var request = new RegisterRequest
        {
            Username = "takenuser",
            Email = "unique@example.com",
            Password = "Password@1!",
            DisplayName = "Unique User"
        };

        var result = await _service.RegisterAsync(request, isAdminRegistration: true);

        result.Success.Should().BeFalse();
        result.Error.Should().Contain("Username already taken");
    }

    [Fact]
    public async Task RegisterAsync_NonAdmin_RequiresInviteCode()
    {
        var request = new RegisterRequest
        {
            Username = "nocode",
            Email = "nocode@example.com",
            Password = "Password@1!",
            DisplayName = "No Code User"
        };

        var result = await _service.RegisterAsync(request, isAdminRegistration: false);

        result.Success.Should().BeFalse();
        result.Error.Should().Contain("Invite code is required");
    }

    [Fact]
    public async Task RegisterAsync_ValidInviteCode_CreatesUser()
    {
        SeedOrganization(orgId: 2, name: "Invite Org");

        var invite = new OrganizationInvite
        {
            OrganizationId = 2,
            Email = "invited@example.com",
            InviteCode = "VALID-CODE-123",
            OrgRole = "member",
            InvitedBy = 1,
            ExpiresAt = DateTime.UtcNow.AddDays(7),
            CreatedAt = DateTime.UtcNow
        };
        _context.OrganizationInvites.Add(invite);
        _context.SaveChanges();

        var request = new RegisterRequest
        {
            Username = "inviteduser",
            Email = "invited@example.com",
            Password = "Password@1!",
            DisplayName = "Invited User",
            InviteCode = "VALID-CODE-123"
        };

        var result = await _service.RegisterAsync(request, isAdminRegistration: false);

        result.Success.Should().BeTrue();
        var user = await _context.AppUsers.FirstOrDefaultAsync(u => u.Username == "inviteduser");
        user.Should().NotBeNull();
        user!.OrganizationId.Should().Be(2);
    }

    [Fact]
    public async Task RegisterAsync_ExpiredInviteCode_Fails()
    {
        var invite = new OrganizationInvite
        {
            OrganizationId = 1,
            Email = "expired@example.com",
            InviteCode = "EXPIRED-CODE",
            OrgRole = "member",
            InvitedBy = 1,
            ExpiresAt = DateTime.UtcNow.AddDays(-1),
            CreatedAt = DateTime.UtcNow.AddDays(-8)
        };
        _context.OrganizationInvites.Add(invite);
        _context.SaveChanges();

        var request = new RegisterRequest
        {
            Username = "expireduser",
            Email = "expired@example.com",
            Password = "Password@1!",
            DisplayName = "Expired User",
            InviteCode = "EXPIRED-CODE"
        };

        var result = await _service.RegisterAsync(request, isAdminRegistration: false);

        result.Success.Should().BeFalse();
        result.Error.Should().Contain("Invalid or expired invite code");
    }

    [Fact]
    public async Task RegisterAsync_InviteEmailMismatch_Fails()
    {
        var invite = new OrganizationInvite
        {
            OrganizationId = 1,
            Email = "original@example.com",
            InviteCode = "MISMATCH-CODE",
            OrgRole = "member",
            InvitedBy = 1,
            ExpiresAt = DateTime.UtcNow.AddDays(7),
            CreatedAt = DateTime.UtcNow
        };
        _context.OrganizationInvites.Add(invite);
        _context.SaveChanges();

        var request = new RegisterRequest
        {
            Username = "mismatchuser",
            Email = "different@example.com",
            Password = "Password@1!",
            DisplayName = "Mismatch User",
            InviteCode = "MISMATCH-CODE"
        };

        var result = await _service.RegisterAsync(request, isAdminRegistration: false);

        result.Success.Should().BeFalse();
        result.Error.Should().Contain("Email does not match");
    }

    [Fact]
    public async Task RegisterAsync_CreatesSession()
    {
        var request = new RegisterRequest
        {
            Username = "sessionuser",
            Email = "session@example.com",
            Password = "Password@1!",
            DisplayName = "Session User"
        };

        var result = await _service.RegisterAsync(request, isAdminRegistration: true);

        result.Success.Should().BeTrue();
        var sessions = await _context.AppSessions.Where(s => s.UserId == result.UserId).ToListAsync();
        sessions.Should().HaveCount(1);
    }

    // --- ChangePassword Tests ---

    [Fact]
    public async Task ChangePasswordAsync_ValidCurrentPassword_Succeeds()
    {
        var user = SeedUser(password: "OldPass@123!");

        await _service.ChangePasswordAsync(user.UserId, "OldPass@123!", "NewPass@456!");

        var updatedUser = await _context.AppUsers.FindAsync(user.UserId);
        _service.VerifyPassword("NewPass@456!", updatedUser!.PasswordHash!).Should().BeTrue();
        _service.VerifyPassword("OldPass@123!", updatedUser.PasswordHash!).Should().BeFalse();
    }

    [Fact]
    public async Task ChangePasswordAsync_WrongCurrentPassword_Throws()
    {
        var user = SeedUser();

        var act = () => _service.ChangePasswordAsync(user.UserId, "WrongCurrent!", "NewPass@456!");

        await act.Should().ThrowAsync<InvalidOperationException>()
            .WithMessage("*Current password is incorrect*");
    }

    [Fact]
    public async Task ChangePasswordAsync_SameAsCurrentPassword_Throws()
    {
        var user = SeedUser(password: "SamePass@123!");

        var act = () => _service.ChangePasswordAsync(user.UserId, "SamePass@123!", "SamePass@123!");

        await act.Should().ThrowAsync<InvalidOperationException>()
            .WithMessage("*New password must be different*");
    }

    [Fact]
    public async Task ChangePasswordAsync_NonexistentUser_Throws()
    {
        var act = () => _service.ChangePasswordAsync(999, "Any", "New");

        await act.Should().ThrowAsync<KeyNotFoundException>()
            .WithMessage("*999*");
    }

    [Fact]
    public async Task ChangePasswordAsync_RevokesAllActiveSessions()
    {
        var user = SeedUser(password: "OldPass@123!");

        // Seed two active sessions
        _context.AppSessions.AddRange(
            new AppSession { UserId = user.UserId, TokenHash = "hash1", IssuedAt = DateTime.UtcNow, ExpiresAt = DateTime.UtcNow.AddMinutes(30) },
            new AppSession { UserId = user.UserId, TokenHash = "hash2", IssuedAt = DateTime.UtcNow, ExpiresAt = DateTime.UtcNow.AddMinutes(30) }
        );
        _context.SaveChanges();

        await _service.ChangePasswordAsync(user.UserId, "OldPass@123!", "NewPass@456!");

        var sessions = await _context.AppSessions
            .Where(s => s.UserId == user.UserId)
            .ToListAsync();
        sessions.Should().AllSatisfy(s => s.RevokedAt.Should().NotBeNull());
    }

    // --- GetProfile Tests ---

    [Fact]
    public async Task GetProfileAsync_ExistingUser_ReturnsProfile()
    {
        var user = SeedUser(displayName: "Profile User", email: "profile@example.com");

        var profile = await _service.GetProfileAsync(user.UserId);

        profile.UserId.Should().Be(user.UserId);
        profile.DisplayName.Should().Be("Profile User");
        profile.Email.Should().Be("profile@example.com");
        profile.Username.Should().Be("testuser");
        profile.Role.Should().Be("USER");
        profile.IsOrgAdmin.Should().BeFalse();
    }

    [Fact]
    public async Task GetProfileAsync_AdminUser_ReturnsIsOrgAdminTrue()
    {
        var user = SeedUser(isOrgAdmin: "Y");

        var profile = await _service.GetProfileAsync(user.UserId);

        profile.IsOrgAdmin.Should().BeTrue();
    }

    [Fact]
    public async Task GetProfileAsync_NonexistentUser_Throws()
    {
        var act = () => _service.GetProfileAsync(999);

        await act.Should().ThrowAsync<KeyNotFoundException>()
            .WithMessage("*999*");
    }

    // --- Logout Tests ---

    [Fact]
    public async Task LogoutAsync_ValidSession_RevokesAndReturnsTrue()
    {
        var user = SeedUser();
        var session = new AppSession
        {
            UserId = user.UserId,
            TokenHash = "active-hash",
            IssuedAt = DateTime.UtcNow,
            ExpiresAt = DateTime.UtcNow.AddMinutes(30)
        };
        _context.AppSessions.Add(session);
        _context.SaveChanges();

        var result = await _service.LogoutAsync(user.UserId, "active-hash");

        result.Should().BeTrue();
        var updatedSession = await _context.AppSessions.FindAsync(session.SessionId);
        updatedSession!.RevokedAt.Should().NotBeNull();
    }

    [Fact]
    public async Task LogoutAsync_NoMatchingSession_ReturnsFalse()
    {
        var result = await _service.LogoutAsync(999, "no-such-hash");

        result.Should().BeFalse();
    }

    // --- ValidateSession Tests ---

    [Fact]
    public async Task ValidateSessionAsync_ValidSession_ReturnsTrue()
    {
        // Use a unique high userId to avoid collisions with the static _revokedUsers
        // dictionary that persists across test instances (populated by ChangePassword/RevokeAll tests).
        var user = SeedUser(userId: 9001, email: "validate@example.com", username: "validateuser");
        var session = new AppSession
        {
            UserId = user.UserId,
            TokenHash = "valid-token-hash",
            IssuedAt = DateTime.UtcNow,
            ExpiresAt = DateTime.UtcNow.AddMinutes(30)
        };
        _context.AppSessions.Add(session);
        _context.SaveChanges();

        var result = await _service.ValidateSessionAsync(user.UserId, "valid-token-hash");

        result.Should().BeTrue();
    }

    [Fact]
    public async Task ValidateSessionAsync_ExpiredSession_ReturnsFalse()
    {
        var user = SeedUser(userId: 9002, email: "expired@example.com", username: "expireduser");
        var session = new AppSession
        {
            UserId = user.UserId,
            TokenHash = "expired-hash",
            IssuedAt = DateTime.UtcNow.AddHours(-2),
            ExpiresAt = DateTime.UtcNow.AddMinutes(-30)
        };
        _context.AppSessions.Add(session);
        _context.SaveChanges();

        var result = await _service.ValidateSessionAsync(user.UserId, "expired-hash");

        result.Should().BeFalse();
    }

    [Fact]
    public async Task ValidateSessionAsync_RevokedSession_ReturnsFalse()
    {
        var user = SeedUser(userId: 9003, email: "revoked@example.com", username: "revokeduser");
        var session = new AppSession
        {
            UserId = user.UserId,
            TokenHash = "revoked-hash",
            IssuedAt = DateTime.UtcNow,
            ExpiresAt = DateTime.UtcNow.AddMinutes(30),
            RevokedAt = DateTime.UtcNow.AddMinutes(-5)
        };
        _context.AppSessions.Add(session);
        _context.SaveChanges();

        var result = await _service.ValidateSessionAsync(user.UserId, "revoked-hash");

        result.Should().BeFalse();
    }

    [Fact]
    public async Task ValidateSessionAsync_NonexistentSession_ReturnsFalse()
    {
        var result = await _service.ValidateSessionAsync(99999, "nonexistent-hash");

        result.Should().BeFalse();
    }

    // --- RefreshToken Tests ---

    [Fact]
    public async Task RefreshTokenAsync_ValidRefreshToken_ReturnsNewTokens()
    {
        var user = SeedUser();

        // Login to create a session with refresh token hash
        var loginResult = await _service.LoginAsync("test@example.com", TestPassword);
        loginResult.Success.Should().BeTrue();

        // Compute the hash of the refresh token the same way the service does
        var refreshTokenHash = ComputeSha256Hash(loginResult.RefreshToken!);

        var result = await _service.RefreshTokenAsync(refreshTokenHash);

        result.Success.Should().BeTrue();
        result.Token.Should().NotBeNullOrEmpty();
        result.RefreshToken.Should().NotBeNullOrEmpty();
        result.UserId.Should().Be(user.UserId);
    }

    [Fact]
    public async Task RefreshTokenAsync_InvalidToken_ReturnsFailure()
    {
        var result = await _service.RefreshTokenAsync("nonexistent-refresh-hash");

        result.Success.Should().BeFalse();
        result.Error.Should().Contain("Invalid refresh token");
    }

    [Fact]
    public async Task RefreshTokenAsync_RotatesOldSession()
    {
        var user = SeedUser();

        var loginResult = await _service.LoginAsync("test@example.com", TestPassword);
        var refreshTokenHash = ComputeSha256Hash(loginResult.RefreshToken!);

        var refreshResult = await _service.RefreshTokenAsync(refreshTokenHash);

        refreshResult.Success.Should().BeTrue();

        // Old session should be revoked
        var sessions = await _context.AppSessions
            .Where(s => s.UserId == user.UserId)
            .OrderBy(s => s.SessionId)
            .ToListAsync();

        // Should have login session (revoked) + new session from refresh
        sessions.Should().HaveCountGreaterThanOrEqualTo(2);
        sessions.First().RevokedAt.Should().NotBeNull();
        sessions.Last().RevokedAt.Should().BeNull();
    }

    // --- RevokeAllUserSessions Tests ---

    [Fact]
    public async Task RevokeAllUserSessionsAsync_RevokesAllSessions()
    {
        var user = SeedUser();
        _context.AppSessions.AddRange(
            new AppSession { UserId = user.UserId, TokenHash = "s1", IssuedAt = DateTime.UtcNow, ExpiresAt = DateTime.UtcNow.AddMinutes(30) },
            new AppSession { UserId = user.UserId, TokenHash = "s2", IssuedAt = DateTime.UtcNow, ExpiresAt = DateTime.UtcNow.AddMinutes(30) },
            new AppSession { UserId = user.UserId, TokenHash = "s3", IssuedAt = DateTime.UtcNow, ExpiresAt = DateTime.UtcNow.AddMinutes(30) }
        );
        _context.SaveChanges();

        await _service.RevokeAllUserSessionsAsync(user.UserId, "test_reason");

        var sessions = await _context.AppSessions
            .Where(s => s.UserId == user.UserId)
            .ToListAsync();
        sessions.Should().AllSatisfy(s => s.RevokedAt.Should().NotBeNull());
    }

    // --- UpdateProfile Tests ---

    [Fact]
    public async Task UpdateProfileAsync_UpdatesDisplayName()
    {
        var user = SeedUser(displayName: "Old Name");

        var request = new UpdateProfileRequest { DisplayName = "New Name" };
        var result = await _service.UpdateProfileAsync(user.UserId, request);

        result.DisplayName.Should().Be("New Name");
    }

    [Fact]
    public async Task UpdateProfileAsync_NonexistentUser_Throws()
    {
        var request = new UpdateProfileRequest { DisplayName = "Name" };

        var act = () => _service.UpdateProfileAsync(999, request);

        await act.Should().ThrowAsync<KeyNotFoundException>()
            .WithMessage("*999*");
    }

    /// <summary>
    /// Helper to compute SHA-256 hash, matching the private method in AuthService.
    /// </summary>
    private static string ComputeSha256Hash(string input)
    {
        var bytes = System.Security.Cryptography.SHA256.HashData(
            System.Text.Encoding.UTF8.GetBytes(input));
        return Convert.ToHexStringLower(bytes);
    }
}
