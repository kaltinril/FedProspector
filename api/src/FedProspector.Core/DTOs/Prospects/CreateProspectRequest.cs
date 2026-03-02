namespace FedProspector.Core.DTOs.Prospects;

public class CreateProspectRequest
{
    public string NoticeId { get; set; } = string.Empty;
    public int? AssignedTo { get; set; }
    public int? CaptureManagerId { get; set; }
    public string? Priority { get; set; } = "MEDIUM";
    public string? Notes { get; set; }
}
