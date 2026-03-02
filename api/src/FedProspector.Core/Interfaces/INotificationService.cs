using FedProspector.Core.DTOs.Notifications;

namespace FedProspector.Core.Interfaces;

public interface INotificationService
{
    Task<NotificationListResponse> GetNotificationsAsync(int userId, NotificationListRequest request);
    Task MarkAsReadAsync(int userId, int notificationId);
    Task MarkAllAsReadAsync(int userId);
    Task<int> GetUnreadCountAsync(int userId);
    Task CreateNotificationAsync(int userId, string type, string title, string? message = null, string? entityType = null, string? entityId = null);
}
