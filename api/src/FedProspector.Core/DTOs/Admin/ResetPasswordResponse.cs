namespace FedProspector.Core.DTOs.Admin;

public class ResetPasswordResponse
{
    public string Message { get; set; } = string.Empty;

    /// <summary>
    /// The generated temporary password. Shown once in the API response so the admin
    /// can deliver it to the user through a secure channel (standard IAM pattern).
    /// </summary>
    public string TemporaryPassword { get; set; } = string.Empty;
}
