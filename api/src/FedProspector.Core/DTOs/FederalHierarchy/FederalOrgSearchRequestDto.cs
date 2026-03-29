namespace FedProspector.Core.DTOs.FederalHierarchy;

public class FederalOrgSearchRequestDto : PagedRequest
{
    public string? Keyword { get; set; }
    public string? FhOrgType { get; set; }
    public string? Status { get; set; }
    public string? AgencyCode { get; set; }
    public string? Cgac { get; set; }
    public int? Level { get; set; }
    public int? ParentOrgId { get; set; }
}
