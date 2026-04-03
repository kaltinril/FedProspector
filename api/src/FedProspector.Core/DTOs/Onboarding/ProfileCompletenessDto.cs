namespace FedProspector.Core.DTOs.Onboarding;

public class ProfileCompletenessDto
{
    public int OrganizationId { get; set; }
    public string? OrganizationName { get; set; }
    public decimal CompletenessPct { get; set; }
    public bool HasUei { get; set; }
    public bool HasCageCode { get; set; }
    public bool HasNaics { get; set; }
    public bool HasPsc { get; set; }
    public bool HasCertifications { get; set; }
    public bool HasPastPerformance { get; set; }
    public bool HasAddress { get; set; }
    public bool HasBusinessType { get; set; }
    public bool HasSizeStandard { get; set; }
    public List<string> MissingFields { get; set; } = new();
}
