namespace FedProspector.Core.DTOs.Notifications;

public class NotificationListResponse
{
    public PagedResponse<NotificationDto> Notifications { get; set; } = new();
    public int UnreadCount { get; set; }
}
