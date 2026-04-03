namespace FedProspector.Core.DTOs.Onboarding;

public class UeiImportResultDto
{
    public string Uei { get; set; } = string.Empty;
    public bool EntityFound { get; set; }
    public List<string> FieldsPopulated { get; set; } = new();
    public int NaicsCodesImported { get; set; }
    public int CertificationsImported { get; set; }
    public string? Message { get; set; }
}
