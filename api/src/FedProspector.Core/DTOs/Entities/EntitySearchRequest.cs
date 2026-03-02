using FedProspector.Core.DTOs;

namespace FedProspector.Core.DTOs.Entities;

public class EntitySearchRequest : PagedRequest
{
    public string? Name { get; set; }
    public string? Uei { get; set; }
    public string? Naics { get; set; }
    public string? State { get; set; }
    public string? BusinessType { get; set; }
    public string? SbaCertification { get; set; }
    public string? RegistrationStatus { get; set; }
}
