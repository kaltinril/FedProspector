namespace FedProspector.Core.DTOs.Dashboard;

public class SavedSearchSummaryDto
{
    public int SearchId { get; set; }
    public string SearchName { get; set; } = string.Empty;
    public string? Username { get; set; }
    public DateTime? LastRunAt { get; set; }
    public int? LastNewResults { get; set; }
}
