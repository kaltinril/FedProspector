using System.Text.Json;
using FedProspector.Core.Interfaces;
using FedProspector.Core.Models;
using FedProspector.Infrastructure.Data;
using Microsoft.Extensions.Logging;

namespace FedProspector.Infrastructure.Services;

public class ActivityLogService : IActivityLogService
{
    private readonly FedProspectorDbContext _context;
    private readonly ILogger<ActivityLogService> _logger;

    public ActivityLogService(FedProspectorDbContext context, ILogger<ActivityLogService> logger)
    {
        _context = context;
        _logger = logger;
    }

    public async Task LogAsync(int? userId, string action, string entityType, string? entityId, object? details = null, string? ipAddress = null)
    {
        try
        {
            var entry = new ActivityLog
            {
                OrganizationId = 1, // Default org for legacy calls without orgId
                UserId = userId,
                Action = action,
                EntityType = entityType,
                EntityId = entityId,
                Details = details is not null ? JsonSerializer.Serialize(details) : null,
                IpAddress = ipAddress,
                CreatedAt = DateTime.UtcNow
            };

            _context.ActivityLogs.Add(entry);
            await _context.SaveChangesAsync();
        }
        catch (Exception ex)
        {
            // Fire-and-forget: logging failures must never crash the caller
            _logger.LogError(ex, "Failed to write activity log: {Action} {EntityType} {EntityId}", action, entityType, entityId);
        }
    }

    public async Task LogAsync(int organizationId, int? userId, string action, string entityType, string? entityId, object? details = null, string? ipAddress = null)
    {
        try
        {
            var entry = new ActivityLog
            {
                OrganizationId = organizationId,
                UserId = userId,
                Action = action,
                EntityType = entityType,
                EntityId = entityId,
                Details = details is not null ? JsonSerializer.Serialize(details) : null,
                IpAddress = ipAddress,
                CreatedAt = DateTime.UtcNow
            };

            _context.ActivityLogs.Add(entry);
            await _context.SaveChangesAsync();
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to write activity log: {Action} {EntityType} {EntityId}", action, entityType, entityId);
        }
    }
}
