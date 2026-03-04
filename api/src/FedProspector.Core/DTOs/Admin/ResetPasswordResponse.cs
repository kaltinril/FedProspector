namespace FedProspector.Core.DTOs.Admin;

public class ResetPasswordResponse
{
    // TemporaryPassword is intentionally omitted from the response.
    // The password is sent via email (or logged at DEBUG level for local dev).
    public string Message { get; set; } = string.Empty;
}
