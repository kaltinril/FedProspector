namespace FedProspector.Core.DTOs.Admin;

public class ResetPasswordResponse
{
    public string TemporaryPassword { get; set; } = string.Empty;
    public string Message { get; set; } = string.Empty;
}
