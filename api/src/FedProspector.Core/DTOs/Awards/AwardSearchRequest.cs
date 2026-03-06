using FedProspector.Core.DTOs;

namespace FedProspector.Core.DTOs.Awards;

public class AwardSearchRequest : PagedRequest
{
    public string? Piid { get; set; }
    public string? Solicitation { get; set; }
    public string? Naics { get; set; }
    public string? Agency { get; set; }
    public string? VendorUei { get; set; }
    public string? VendorName { get; set; }
    public string? SetAside { get; set; }
    public decimal? MinValue { get; set; }
    public decimal? MaxValue { get; set; }
    public DateOnly? DateFrom { get; set; }
    public DateOnly? DateTo { get; set; }
}
