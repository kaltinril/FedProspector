namespace FedProspector.Core.DTOs.Dashboard;

public class DueOpportunityDto
{
    public int ProspectId { get; set; }
    public string? Status { get; set; }
    public string? Priority { get; set; }
    public string? Title { get; set; }
    public DateTime? ResponseDeadline { get; set; }
    public string? SetAsideCode { get; set; }
    public string? AssignedTo { get; set; }
}
