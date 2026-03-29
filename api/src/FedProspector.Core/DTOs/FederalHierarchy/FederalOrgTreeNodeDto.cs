namespace FedProspector.Core.DTOs.FederalHierarchy;

public class FederalOrgTreeNodeDto
{
    public int FhOrgId { get; set; }
    public string? FhOrgName { get; set; }
    public int ChildCount { get; set; }
    public int DescendantCount { get; set; }
}
