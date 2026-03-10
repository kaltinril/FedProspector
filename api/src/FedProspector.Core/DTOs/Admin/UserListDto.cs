namespace FedProspector.Core.DTOs.Admin;

public class UserListDto
{
    public int UserId { get; set; }
    public string Username { get; set; } = string.Empty;
    public string DisplayName { get; set; } = string.Empty;
    public string? Email { get; set; }
    public string Role { get; set; } = "USER";
    public bool IsActive { get; set; }
    public bool IsOrgAdmin { get; set; }
    public DateTime? LastLoginAt { get; set; }
    public DateTime? CreatedAt { get; set; }
}
