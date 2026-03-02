namespace FedProspector.Core.DTOs.Prospects;

public class UpdateProspectStatusRequest
{
    public string NewStatus { get; set; } = string.Empty;
    public string? Notes { get; set; }
}
