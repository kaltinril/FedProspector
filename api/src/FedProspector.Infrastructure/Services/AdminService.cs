using System.Security.Cryptography;
using FedProspector.Core.Constants;
using FedProspector.Core.DTOs;
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
    private readonly IActivityLogService _activityLogService;

    // Shared with HealthController — single source of truth in EtlStalenessThresholds.All
    private static readonly Dictionary<string, (string Label, double ThresholdHours)> StalenessThresholds
        = EtlStalenessThresholds.All;

    public AdminService(
        FedProspectorDbContext context,
        ILogger<AdminService> logger,
        IAuthService authService,
        IActivityLogService activityLogService)
    {
        _context = context;
        _logger = logger;
        _authService = authService;
        _activityLogService = activityLogService;
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

    public async Task<PagedResponse<UserListDto>> GetUsersAsync(int organizationId, int page = 1, int pageSize = 25)
    {
        page = page < 1 ? 1 : page;
        pageSize = pageSize < 1 ? 1 : pageSize > 100 ? 100 : pageSize;

        var query = _context.AppUsers.AsNoTracking()
            .Where(u => u.OrganizationId == organizationId);

        var totalCount = await query.CountAsync();

        var items = await query
            .OrderBy(u => u.Username)
            .Skip((page - 1) * pageSize)
            .Take(pageSize)
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

        return new PagedResponse<UserListDto>
        {
            Items = items,
            Page = page,
            PageSize = pageSize,
            TotalCount = totalCount
        };
    }

    public async Task<UserListDto> UpdateUserAsync(int userId, UpdateUserRequest request, int adminUserId, int adminOrgId)
    {
        var user = await _context.AppUsers.FindAsync(userId)
            ?? throw new KeyNotFoundException($"User {userId} not found.");

        if (user.OrganizationId != adminOrgId)
            throw new UnauthorizedAccessException("Cannot modify users from other organizations.");

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

                // Revoke all active sessions for deactivated user
                var activeSessions = await _context.AppSessions
                    .Where(s => s.UserId == userId && s.RevokedAt == null)
                    .ToListAsync();
                foreach (var session in activeSessions)
                {
                    session.RevokedAt = DateTime.UtcNow;
                }
            }
        }

        user.UpdatedAt = DateTime.UtcNow;
        await _context.SaveChangesAsync();

        _logger.LogInformation("Admin {AdminUserId} updated user {UserId}", adminUserId, userId);

        await _activityLogService.LogAsync(adminUserId, "ADMIN_UPDATE_USER", "USER", userId.ToString(),
            new { request.Role, request.IsAdmin, request.IsActive });

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

    public async Task<ResetPasswordResponse> ResetPasswordAsync(int userId, int adminUserId, int adminOrgId)
    {
        var user = await _context.AppUsers.FindAsync(userId)
            ?? throw new KeyNotFoundException($"User {userId} not found.");

        if (user.OrganizationId != adminOrgId)
            throw new UnauthorizedAccessException("Cannot modify users from other organizations.");

        if (userId == adminUserId)
            throw new InvalidOperationException("Cannot reset your own password. Use change-password instead.");

        var tempPassword = GenerateTemporaryPassword(12);
        user.PasswordHash = _authService.HashPassword(tempPassword);
        user.ForcePasswordChange = "Y";
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

        await _activityLogService.LogAsync(adminUserId, "ADMIN_RESET_PASSWORD", "USER", userId.ToString(),
            new { TargetUsername = user.Username, SessionsRevoked = activeSessions.Count });

        return new ResetPasswordResponse
        {
            Message = $"Password reset for user '{user.Username}'. Provide temporary credentials to user securely.",
            TemporaryPassword = tempPassword
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

    public async Task<LoadHistoryResponse> GetLoadHistoryAsync(string? source, string? status, int days, int limit, int offset)
    {
        days = days < 1 ? 7 : days;
        limit = limit < 1 ? 1 : limit > 100 ? 100 : limit;
        offset = offset < 0 ? 0 : offset;

        var cutoff = DateTime.Now.AddDays(-days);

        var query = _context.EtlLoadLogs.AsNoTracking()
            .Where(l => l.StartedAt >= cutoff);

        if (!string.IsNullOrWhiteSpace(source))
            query = query.Where(l => l.SourceSystem == source);

        if (!string.IsNullOrWhiteSpace(status))
            query = query.Where(l => l.Status == status);

        var totalCount = await query.CountAsync();

        var items = await query
            .OrderByDescending(l => l.StartedAt)
            .Skip(offset)
            .Take(limit)
            .Select(l => new LoadHistoryDto
            {
                LoadId = l.LoadId,
                SourceSystem = l.SourceSystem,
                LoadType = l.LoadType,
                Status = l.Status,
                StartedAt = l.StartedAt,
                CompletedAt = l.CompletedAt,
                DurationSeconds = l.CompletedAt != null
                    ? (l.CompletedAt.Value - l.StartedAt).TotalSeconds
                    : null,
                RecordsRead = l.RecordsRead,
                RecordsInserted = l.RecordsInserted,
                RecordsUpdated = l.RecordsUpdated,
                RecordsErrored = l.RecordsErrored,
                ErrorMessage = l.ErrorMessage
            })
            .ToListAsync();

        return new LoadHistoryResponse
        {
            Items = items,
            TotalCount = totalCount
        };
    }

    public async Task<List<HealthSnapshotDto>> GetHealthSnapshotsAsync(int days)
    {
        days = days < 1 ? 30 : days;
        var cutoff = DateTime.Now.AddDays(-days);

        return await _context.EtlHealthSnapshots.AsNoTracking()
            .Where(s => s.CheckedAt >= cutoff)
            .OrderByDescending(s => s.CheckedAt)
            .Select(s => new HealthSnapshotDto
            {
                SnapshotId = s.SnapshotId,
                CheckedAt = s.CheckedAt,
                OverallStatus = s.OverallStatus,
                AlertCount = s.AlertCount,
                ErrorCount = s.ErrorCount,
                StaleSourceCount = s.StaleSourceCount,
                Details = s.Details
            })
            .ToListAsync();
    }

    public async Task<List<ApiKeyStatusDto>> GetApiKeyStatusAsync()
    {
        var today = DateOnly.FromDateTime(DateTime.UtcNow);

        return await _context.EtlRateLimits.AsNoTracking()
            .Where(r => r.RequestDate == today)
            .Select(r => new ApiKeyStatusDto
            {
                SourceSystem = r.SourceSystem,
                DailyLimit = r.MaxRequests,
                RequestsMade = r.RequestsMade,
                Remaining = Math.Max(0, r.MaxRequests - r.RequestsMade),
                LastRequestAt = r.LastRequestAt
            })
            .ToListAsync();
    }

    public async Task<List<JobStatusDto>> GetJobStatusAsync()
    {
        // Two-step approach: get aggregates, then get latest row per group
        var groups = await _context.EtlLoadLogs.AsNoTracking()
            .GroupBy(l => new { l.SourceSystem, l.LoadType })
            .Select(g => new
            {
                g.Key.SourceSystem,
                g.Key.LoadType,
                RunCount = g.Count(),
                LastStartedAt = g.Max(l => l.StartedAt)
            })
            .ToListAsync();

        var result = new List<JobStatusDto>();
        foreach (var g in groups)
        {
            var latest = await _context.EtlLoadLogs.AsNoTracking()
                .Where(l => l.SourceSystem == g.SourceSystem
                         && l.LoadType == g.LoadType
                         && l.StartedAt == g.LastStartedAt)
                .FirstOrDefaultAsync();

            if (latest == null) continue;

            result.Add(new JobStatusDto
            {
                SourceSystem = g.SourceSystem,
                LoadType = g.LoadType,
                LastRunAt = latest.StartedAt,
                LastStatus = latest.Status,
                LastDurationSeconds = latest.CompletedAt != null
                    ? (latest.CompletedAt.Value - latest.StartedAt).TotalSeconds
                    : null,
                RecordsProcessed = latest.RecordsInserted + latest.RecordsUpdated,
                RunCount = g.RunCount
            });
        }

        return result.OrderBy(j => j.SourceSystem).ThenBy(j => j.LoadType).ToList();
    }

    private async Task<List<EtlSourceStatusDto>> GetSourceStatusesAsync()
    {
        // Get latest successful load per source (two-step to avoid untranslatable LINQ)
        // Step 1: Get the max CompletedAt per source
        var latestBySource = await _context.EtlLoadLogs.AsNoTracking()
            .Where(l => l.Status == "SUCCESS")
            .GroupBy(l => l.SourceSystem)
            .Select(g => new
            {
                SourceSystem = g.Key,
                LastLoadAt = g.Max(l => l.CompletedAt)
            })
            .ToListAsync();

        // Step 2: For each source, fetch RecordsProcessed from the latest load row
        var latestLoads = new List<LatestLoadInfo>();
        foreach (var src in latestBySource)
        {
            var recordsProcessed = await _context.EtlLoadLogs.AsNoTracking()
                .Where(l => l.SourceSystem == src.SourceSystem
                         && l.CompletedAt == src.LastLoadAt
                         && l.Status == "SUCCESS")
                .Select(l => l.RecordsInserted + l.RecordsUpdated)
                .FirstOrDefaultAsync();
            latestLoads.Add(new LatestLoadInfo
            {
                SourceSystem = src.SourceSystem,
                LastLoadAt = src.LastLoadAt,
                RecordsProcessed = recordsProcessed
            });
        }

        var sources = new List<EtlSourceStatusDto>();
        // Python ETL stores timestamps in local time, so compare with local time
        var now = DateTime.Now;

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

internal class LatestLoadInfo
{
    public string SourceSystem { get; set; } = string.Empty;
    public DateTime? LastLoadAt { get; set; }
    public int RecordsProcessed { get; set; }
}

internal static class StringExtensions
{
    public static string? Truncate(this string? value, int maxLength)
    {
        if (string.IsNullOrEmpty(value)) return value;
        return value.Length <= maxLength ? value : value[..maxLength] + "...";
    }
}
