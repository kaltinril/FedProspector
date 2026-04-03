namespace FedProspector.Core.DTOs.Onboarding;

public class OrganizationPscDto
{
    public int OrganizationPscId { get; set; }
    public string PscCode { get; set; } = string.Empty;
    public DateTime? AddedAt { get; set; }
}
