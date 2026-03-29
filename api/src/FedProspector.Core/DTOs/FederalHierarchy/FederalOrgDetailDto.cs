namespace FedProspector.Core.DTOs.FederalHierarchy;

public class FederalOrgDetailDto
{
    public int FhOrgId { get; set; }
    public string? FhOrgName { get; set; }
    public string? FhOrgType { get; set; }
    public string? Status { get; set; }
    public string? AgencyCode { get; set; }
    public string? Cgac { get; set; }
    public int? Level { get; set; }
    public int? ParentOrgId { get; set; }
    public string? Description { get; set; }
    public string? OldfpdsOfficeCode { get; set; }
    public DateOnly? CreatedDate { get; set; }
    public DateOnly? LastModifiedDate { get; set; }
    public DateTime? LastLoadedAt { get; set; }
    public int ChildCount { get; set; }
    public List<FederalOrgBreadcrumbDto> ParentChain { get; set; } = [];
}
