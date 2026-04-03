namespace FedProspector.Core.DTOs.Pipeline;

public class StaleProspectDto
{
    public int ProspectId { get; set; }
    public string NoticeId { get; set; } = string.Empty;
    public string? OpportunityTitle { get; set; }
    public string Status { get; set; } = string.Empty;
    public string? Priority { get; set; }
    public int DaysSinceUpdate { get; set; }
    public int? AssignedTo { get; set; }
    public string? AssignedToName { get; set; }
    public decimal? EstimatedValue { get; set; }
    public DateTime LastUpdatedAt { get; set; }
}
