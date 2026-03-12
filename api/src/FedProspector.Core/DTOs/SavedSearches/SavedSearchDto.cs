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

    // Auto-prospect fields (Phase 91)
    public string AutoProspectEnabled { get; set; } = "N";
    public decimal MinPwinScore { get; set; } = 30.0m;
    public int? AutoAssignTo { get; set; }
    public DateTime? LastAutoRunAt { get; set; }
    public int? LastAutoCreated { get; set; }
}
