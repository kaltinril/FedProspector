namespace FedProspector.Core.DTOs.FederalHierarchy;

public class FederalOrgBreadcrumbDto
{
    public int FhOrgId { get; set; }
    public string? FhOrgName { get; set; }
    public string? FhOrgType { get; set; }
    public int? Level { get; set; }
}
