namespace FedProspector.Core.DTOs;

public class UpdateProfileRequest
{
    public string? DisplayName { get; set; }
    public string? Email { get; set; }

    /// <summary>
    /// Required when changing email address. Verified against current password for security.
    /// </summary>
    public string? CurrentPassword { get; set; }
}
