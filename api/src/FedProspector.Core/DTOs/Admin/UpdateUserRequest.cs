namespace FedProspector.Core.DTOs.Admin;

public class UpdateUserRequest
{
    public string? Role { get; set; }
    public bool? IsOrgAdmin { get; set; }
    public bool? IsActive { get; set; }
}
