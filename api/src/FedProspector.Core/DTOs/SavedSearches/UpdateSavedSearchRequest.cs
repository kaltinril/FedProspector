namespace FedProspector.Core.DTOs.SavedSearches;

public class UpdateSavedSearchRequest
{
    public string? Name { get; set; }
    public string? Description { get; set; }
    // Typed as SavedSearchFilterCriteria (same as CreateSavedSearchRequest) so that
    // JSON validation, round-tripping, and service serialization are consistent.
    public SavedSearchFilterCriteria? FilterCriteria { get; set; }
    public bool? NotificationsEnabled { get; set; }
}
