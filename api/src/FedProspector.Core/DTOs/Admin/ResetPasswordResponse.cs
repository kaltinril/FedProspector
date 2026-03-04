namespace FedProspector.Core.DTOs.Admin;

public class ResetPasswordResponse
{
    // TemporaryPassword is intentionally omitted from the response.
    // Admin must deliver temporary credentials to the user through a secure channel.
    public string Message { get; set; } = string.Empty;
}
