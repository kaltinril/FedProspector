using FedProspector.Core.DTOs.Opportunities;

namespace FedProspector.Core.DTOs.SavedSearches;

public class SavedSearchRunResultDto
{
    public int SearchId { get; set; }
    public string SearchName { get; set; } = string.Empty;
    public List<OpportunitySearchDto> Results { get; set; } = [];
    public int TotalCount { get; set; }
    public int NewCount { get; set; }
    public DateTime ExecutedAt { get; set; } = DateTime.UtcNow;
}
