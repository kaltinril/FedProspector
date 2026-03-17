namespace FedProspector.Core.DTOs;

public class AuthResult
{
    public bool Success { get; set; }
    public string? Token { get; set; }
    public string? RefreshToken { get; set; }
    public string? Error { get; set; }
    public int? UserId { get; set; }
    public string? UserName { get; set; }
    public DateTime? ExpiresAt { get; set; }
    public bool ForcePasswordChange { get; set; }
}
