using FedProspector.Core.DTOs;

namespace FedProspector.Core.DTOs.Opportunities;

public class TargetOpportunitySearchRequest : PagedRequest
{
    public decimal? MinValue { get; set; }
    public decimal? MaxValue { get; set; }
    public string? NaicsSector { get; set; }
    public string? SetAside { get; set; }
    public string? Naics { get; set; }
    public string? Department { get; set; }
    public string? State { get; set; }
}
