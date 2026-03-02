namespace FedProspector.Core.DTOs.Proposals;

public class CreateMilestoneRequest
{
    public string Title { get; set; } = string.Empty;
    public DateTime DueDate { get; set; }
    public string? AssignedTo { get; set; }
}
