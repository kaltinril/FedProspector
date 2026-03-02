namespace FedProspector.Core.DTOs.Proposals;

public class UpdateMilestoneRequest
{
    public DateOnly? CompletedDate { get; set; }
    public string? Status { get; set; }
    public string? Notes { get; set; }
}
