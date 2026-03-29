namespace FedProspector.Core.DTOs.FederalHierarchy;

public class FederalOrgListItemDto
{
    public int FhOrgId { get; set; }
    public string? FhOrgName { get; set; }
    public string? FhOrgType { get; set; }
    public string? Status { get; set; }
    public string? AgencyCode { get; set; }
    public string? Cgac { get; set; }
    public int? Level { get; set; }
    public int? ParentOrgId { get; set; }
    public int? ChildCount { get; set; }
    public int? OpportunityCount { get; set; }
    public int? AwardCount { get; set; }
}
