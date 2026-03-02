namespace FedProspector.Core.DTOs.Organizations;

public class InviteDto
{
    public int InviteId { get; set; }
    public string Email { get; set; } = string.Empty;
    public string OrgRole { get; set; } = string.Empty;
    public string? InvitedByName { get; set; }
    public DateTime ExpiresAt { get; set; }
    public DateTime CreatedAt { get; set; }
}
