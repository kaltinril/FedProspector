namespace FedProspector.Core.DTOs.Proposals;

public class ProposalMilestoneDto
{
    public int MilestoneId { get; set; }
    public string MilestoneName { get; set; } = string.Empty;
    public DateOnly? DueDate { get; set; }
    public DateOnly? CompletedDate { get; set; }
    public int? AssignedTo { get; set; }
    public string Status { get; set; } = string.Empty;
    public string? Notes { get; set; }
    public DateTime? CreatedAt { get; set; }
}
