using FedProspector.Core.DTOs;

namespace FedProspector.Core.DTOs.Subawards;

public class TeamingPartnerSearchRequest : PagedRequest
{
    public string? Naics { get; set; }
    public int MinSubawards { get; set; } = 2;
    public string? PrimeUei { get; set; }
    public string? SubUei { get; set; }
}
