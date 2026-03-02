namespace FedProspector.Core.Interfaces;

public interface IActivityLogService
{
    Task LogAsync(int? userId, string action, string entityType, string? entityId, object? details = null, string? ipAddress = null);
    Task LogAsync(int organizationId, int? userId, string action, string entityType, string? entityId, object? details = null, string? ipAddress = null);
}
