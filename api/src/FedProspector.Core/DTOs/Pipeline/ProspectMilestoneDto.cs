namespace FedProspector.Core.DTOs.Pipeline;

public class ProspectMilestoneDto
{
    public int ProspectMilestoneId { get; set; }
    public int ProspectId { get; set; }
    public string MilestoneName { get; set; } = string.Empty;
    public DateOnly TargetDate { get; set; }
    public DateOnly? CompletedDate { get; set; }
    public bool IsCompleted { get; set; }
    public int SortOrder { get; set; }
    public string? Notes { get; set; }
    public DateTime CreatedAt { get; set; }
    public DateTime UpdatedAt { get; set; }
}
