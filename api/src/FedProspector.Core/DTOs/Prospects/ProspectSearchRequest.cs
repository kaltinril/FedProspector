using FedProspector.Core.DTOs;

namespace FedProspector.Core.DTOs.Prospects;

public class ProspectSearchRequest : PagedRequest
{
    public string? Status { get; set; }
    public int? AssignedTo { get; set; }
    public int? CaptureManagerId { get; set; }
    public string? Priority { get; set; }
    public string? Naics { get; set; }
    public string? SetAside { get; set; }
    public bool OpenOnly { get; set; } = true;
}
