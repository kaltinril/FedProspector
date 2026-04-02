using FedProspector.Core.DTOs;

namespace FedProspector.Core.DTOs.Opportunities;

public class OpportunitySearchRequest : PagedRequest
{
    public string? SetAside { get; set; }
    public string? Naics { get; set; }
    public string? Keyword { get; set; }
    public string? Solicitation { get; set; }
    public int? DaysOut { get; set; }
    public bool OpenOnly { get; set; } = true;
    public string? Department { get; set; }
    public string? State { get; set; }
    public bool ExcludeIgnored { get; set; } = true;
}
