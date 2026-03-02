using System.Security.Cryptography;
using FedProspector.Core.DTOs.Admin;
using FedProspector.Core.Interfaces;
using FedProspector.Infrastructure.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;

namespace FedProspector.Infrastructure.Services;

public class AdminService : IAdminService
{
    private readonly FedProspectorDbContext _context;
    private readonly ILogger<AdminService> _logger;
    private readonly IAuthService _authService;

    private static readonly Dictionary<string, (string Label, double ThresholdHours)> StalenessThresholds = new()
    {
        ["SAM_OPPORTUNITY_KEY2"] = ("Opportunities", 6),
        ["SAM_ENTITY"] = ("Entity Data", 48),
        ["SAM_FEDHIER"] = ("Federal Hierarchy", 336),
        ["SAM_AWARDS"] = ("Contract Awards", 336),
        ["GSA_CALC"] = ("CALC+ Labor Rates", 1080),
        ["USASPENDING"] = ("USASpending", 1080),
        ["SAM_EXCLUSIONS"] = ("Exclusions", 336),
        ["SAM_SUBAWARD"] = ("Subaward Data", 336),
    };

    public AdminService(FedProspectorDbContext context, ILogger<AdminService> logger, IAuthService authService)
    {
        _context = context;
        _logger = logger;
        _authService = authService;
    }

    public async Task<EtlStatusDto> GetEtlStatusAsync()
    {
        var sourcesTask = GetSourceStatusesAsync();
        var apiUsageTask = GetApiUsageAsync();
        var errorsTask = GetRecentErrorsAsync();

        await Task.WhenAll(sourcesTask, apiUsageTask, errorsTask);

        var sources = await sourcesTask;
        var apiUsage = await apiUsageTask;
        var errors = await errorsTask;

        // Generate alerts
        var alerts = new List<string>();
        foreach (var source in sources)
        {
            if (source.Status == "STALE")
                alerts.Add($"STALE: {source.Label} — last loaded {source.HoursSinceLoad:F1} hours ago (threshold: {source.ThresholdHours}h)");
            else if (source.Status == "NEVER")
                alerts.Add($"WARN: {source.Label} — never loaded");
        }
        foreach (var err in errors.Take(3))
            alerts.Add($"ERROR: {err.SourceSystem} failed at {err.StartedAt:g} — {err.ErrorMessage.Truncate(100)}");
        foreach (var usage in apiUsage.Where(u => u.Remaining == 0))
            alerts.Add($"WARN: {usage.SourceSystem} — daily API limit exhausted");

        if (alerts.Count == 0)
            alerts.Add("All systems healthy");

        return new EtlStatusDto
        {
            Sources = sources,
            ApiUsage = apiUsage,
            RecentErrors = errors,
            Alerts = alerts
        };
    }

    public async Task<List<UserListDto>> GetUsersAsync()
    {
        return await _context.AppUsers.AsNoTracking()
            .OrderBy(u => u.Username)
            .Select(u => new UserListDto
            {
                UserId = u.UserId,
                Username = u.Username,
                DisplayName = u.DisplayName,
                Email = u.Email,
                Role = u.Role ?? "USER",
                IsActive = u.IsActive == "Y",
                IsAdmin = u.IsAdmin == "Y",
                LastLoginAt = u.LastLoginAt,
                CreatedAt = u.CreatedAt
            })
            .ToListAsync();
    }

    public async Task<UserListDto> UpdateUserAsync(int userId, UpdateUserRequest request, int adminUserId)
    {
        var user = await _context.AppUsers.FindAsync(userId)
            ?? throw new KeyNotFoundException($"User {userId} not found.");

        if (userId == adminUserId && request.IsActive == false)
            throw new InvalidOperationException("Cannot deactivate your own account.");

        if (userId == adminUserId && request.IsAdmin == false)
            throw new InvalidOperationException("Cannot remove your own admin access.");

        if (request.Role != null)
            user.Role = request.Role;

        if (request.IsAdmin.HasValue)
            user.IsAdmin = request.IsAdmin.Value ? "Y" : "N";

        if (request.IsActive.HasValue)
        {
            user.IsActive = request.IsActive.Value ? "Y" : "N";

            if (!request.IsActive.Value)
            {
                user.LockedUntil = null;
                user.FailedLoginAttempts = 0;
            }
        }

        user.UpdatedAt = DateTime.UtcNow;
        await _context.SaveChangesAsync();

        _logger.LogInformation("Admin {AdminUserId} updated user {UserId}", adminUserId, userId);

        return new UserListDto
        {
            UserId = user.UserId,
            Username = user.Username,
            DisplayName = user.DisplayName,
            Email = user.Email,
            Role = user.Role ?? "USER",
            IsActive = user.IsActive == "Y",
            IsAdmin = user.IsAdmin == "Y",
            LastLoginAt = user.LastLoginAt,
            CreatedAt = user.CreatedAt
        };
    }

    public async Task<ResetPasswordResponse> ResetPasswordAsync(int userId, int adminUserId)
    {
        var user = await _context.AppUsers.FindAsync(userId)
            ?? throw new KeyNotFoundException($"User {userId} not found.");

        var tempPassword = GenerateTemporaryPassword(12);
        user.PasswordHash = _authService.HashPassword(tempPassword);
        user.UpdatedAt = DateTime.UtcNow;
        user.FailedLoginAttempts = 0;
        user.LockedUntil = null;

        // Revoke all active sessions for this user
        var activeSessions = await _context.AppSessions
            .Where(s => s.UserId == userId && s.RevokedAt == null)
            .ToListAsync();

        foreach (var session in activeSessions)
            session.RevokedAt = DateTime.UtcNow;

        await _context.SaveChangesAsync();

        _logger.LogInformation("Admin {AdminUserId} reset password for user {UserId}", adminUserId, userId);

        return new ResetPasswordResponse
        {
            TemporaryPassword = tempPassword,
            Message = $"Password reset for user '{user.Username}'. All active sessions have been revoked."
        };
    }

    private static string GenerateTemporaryPassword(int length)
    {
        const string upper = "ABCDEFGHJKLMNPQRSTUVWXYZ";
        const string lower = "abcdefghjkmnpqrstuvwxyz";
        const string digits = "23456789";
        const string special = "!@#$%&*";
        const string allChars = upper + lower + digits + special;

        var password = new char[length];

        // Guarantee at least one of each category
        password[0] = upper[RandomNumberGenerator.GetInt32(upper.Length)];
        password[1] = lower[RandomNumberGenerator.GetInt32(lower.Length)];
        password[2] = digits[RandomNumberGenerator.GetInt32(digits.Length)];
        password[3] = special[RandomNumberGenerator.GetInt32(special.Length)];

        // Fill remaining positions
        for (int i = 4; i < length; i++)
            password[i] = allChars[RandomNumberGenerator.GetInt32(allChars.Length)];

        // Shuffle
        for (int i = length - 1; i > 0; i--)
        {
            int j = RandomNumberGenerator.GetInt32(i + 1);
            (password[i], password[j]) = (password[j], password[i]);
        }

        return new string(password);
    }

    private async Task<List<EtlSourceStatusDto>> GetSourceStatusesAsync()
    {
        // Get latest successful load per source
        var latestLoads = await _context.EtlLoadLogs.AsNoTracking()
            .Where(l => l.Status == "SUCCESS")
            .GroupBy(l => l.SourceSystem)
            .Select(g => new
            {
                SourceSystem = g.Key,
                LastLoadAt = g.Max(l => l.CompletedAt),
                RecordsProcessed = g.OrderByDescending(l => l.CompletedAt)
                    .Select(l => l.RecordsInserted + l.RecordsUpdated)
                    .FirstOrDefault()
            })
            .ToListAsync();

        var sources = new List<EtlSourceStatusDto>();
        var now = DateTime.UtcNow;

        foreach (var (key, (label, threshold)) in StalenessThresholds)
        {
            var load = latestLoads.FirstOrDefault(l => l.SourceSystem == key);
            double? hoursSince = load?.LastLoadAt != null
                ? (now - load.LastLoadAt.Value).TotalHours
                : null;

            string status;
            if (load?.LastLoadAt == null)
                status = "NEVER";
            else if (hoursSince > threshold)
                status = "STALE";
            else if (hoursSince > threshold * 0.8)
                status = "WARNING";
            else
                status = "OK";

            sources.Add(new EtlSourceStatusDto
            {
                SourceSystem = key,
                Label = label,
                LastLoadAt = load?.LastLoadAt,
                HoursSinceLoad = hoursSince.HasValue ? Math.Round(hoursSince.Value, 1) : null,
                ThresholdHours = threshold,
                Status = status,
                RecordsProcessed = load?.RecordsProcessed ?? 0
            });
        }

        return sources;
    }

    private async Task<List<ApiUsageDto>> GetApiUsageAsync()
    {
        var today = DateOnly.FromDateTime(DateTime.UtcNow);
        return await _context.EtlRateLimits.AsNoTracking()
            .Where(r => r.RequestDate == today)
            .Select(r => new ApiUsageDto
            {
                SourceSystem = r.SourceSystem,
                RequestsMade = r.RequestsMade,
                MaxRequests = r.MaxRequests,
                Remaining = Math.Max(0, r.MaxRequests - r.RequestsMade),
                LastRequestAt = r.LastRequestAt
            })
            .ToListAsync();
    }

    private async Task<List<RecentErrorDto>> GetRecentErrorsAsync()
    {
        var cutoff = DateTime.UtcNow.AddDays(-7);
        return await _context.EtlLoadLogs.AsNoTracking()
            .Where(l => l.Status == "FAILED" && l.StartedAt >= cutoff)
            .OrderByDescending(l => l.StartedAt)
            .Take(20)
            .Select(l => new RecentErrorDto
            {
                SourceSystem = l.SourceSystem,
                LoadType = l.LoadType,
                StartedAt = l.StartedAt,
                ErrorMessage = l.ErrorMessage
            })
            .ToListAsync();
    }
}

internal static class StringExtensions
{
    public static string? Truncate(this string? value, int maxLength)
    {
        if (string.IsNullOrEmpty(value)) return value;
        return value.Length <= maxLength ? value : value[..maxLength] + "...";
    }
}
