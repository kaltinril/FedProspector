namespace FedProspector.Core.DTOs.Organizations;

public class CreateInviteRequest
{
    public string Email { get; set; } = string.Empty;
    public string OrgRole { get; set; } = "member";
}
