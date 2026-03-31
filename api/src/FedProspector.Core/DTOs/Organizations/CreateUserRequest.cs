namespace FedProspector.Core.DTOs.Organizations;

public class CreateUserRequest
{
    public string Email { get; set; } = string.Empty;
    public string DisplayName { get; set; } = string.Empty;
    public string Password { get; set; } = string.Empty;
    public string OrgRole { get; set; } = "member";
}
