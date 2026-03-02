namespace FedProspector.Core.DTOs.Admin;

public class UpdateUserRequest
{
    public string? Role { get; set; }
    public bool? IsAdmin { get; set; }
    public bool? IsActive { get; set; }
}
