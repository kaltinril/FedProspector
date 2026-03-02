namespace FedProspector.Core.DTOs.SavedSearches;

public class CreateSavedSearchRequest
{
    public string SearchName { get; set; } = string.Empty;
    public string? Description { get; set; }
    public SavedSearchFilterCriteria FilterCriteria { get; set; } = new();
    public bool NotificationEnabled { get; set; }
}
