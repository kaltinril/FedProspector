namespace FedProspector.Core.DTOs.Dashboard;

public class AssigneeWorkloadDto
{
    public string Username { get; set; } = string.Empty;
    public string? DisplayName { get; set; }
    public int Count { get; set; }
}
