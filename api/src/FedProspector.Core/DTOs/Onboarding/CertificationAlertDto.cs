namespace FedProspector.Core.DTOs.Onboarding;

public class CertificationAlertDto
{
    public string CertificationType { get; set; } = string.Empty;
    public DateTime ExpirationDate { get; set; }
    public int DaysUntilExpiration { get; set; }
    public string AlertLevel { get; set; } = string.Empty;
    public string Source { get; set; } = string.Empty;
}
