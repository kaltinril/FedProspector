namespace FedProspector.Core.DTOs.Notifications;

public class NotificationListRequest : PagedRequest
{
    public bool UnreadOnly { get; set; } = true;
    public string? Type { get; set; }
}
