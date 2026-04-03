namespace FedProspector.Core.DTOs.Pipeline;

public class PipelineCalendarEventDto
{
    public int ProspectId { get; set; }
    public string NoticeId { get; set; } = string.Empty;
    public string? OpportunityTitle { get; set; }
    public DateTime? ResponseDeadline { get; set; }
    public string? SolicitationNumber { get; set; }
    public string Status { get; set; } = string.Empty;
    public string? Priority { get; set; }
    public int? AssignedTo { get; set; }
    public string? AssignedToName { get; set; }
    public decimal? EstimatedValue { get; set; }
    public decimal? WinProbability { get; set; }
}
