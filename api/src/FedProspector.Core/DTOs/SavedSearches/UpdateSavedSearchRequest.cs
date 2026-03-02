namespace FedProspector.Core.DTOs.SavedSearches;

public class UpdateSavedSearchRequest
{
    public string? Name { get; set; }
    public string? Description { get; set; }
    public string? FilterCriteria { get; set; }
    public bool? NotificationsEnabled { get; set; }
}
