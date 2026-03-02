namespace FedProspector.Core.DTOs.SavedSearches;

public class SavedSearchDto
{
    public int SearchId { get; set; }
    public string SearchName { get; set; } = string.Empty;
    public string? Description { get; set; }
    public string FilterCriteria { get; set; } = string.Empty;
    public string? NotificationEnabled { get; set; }
    public string? IsActive { get; set; }
    public DateTime? LastRunAt { get; set; }
    public int? LastNewResults { get; set; }
    public DateTime? CreatedAt { get; set; }
}
