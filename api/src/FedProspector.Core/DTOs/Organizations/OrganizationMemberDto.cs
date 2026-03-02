namespace FedProspector.Core.DTOs.Organizations;

public class OrganizationMemberDto
{
    public int UserId { get; set; }
    public string? Email { get; set; }
    public string DisplayName { get; set; } = string.Empty;
    public string OrgRole { get; set; } = string.Empty;
    public bool IsActive { get; set; }
    public DateTime? CreatedAt { get; set; }
}
