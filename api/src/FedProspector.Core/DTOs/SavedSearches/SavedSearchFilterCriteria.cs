namespace FedProspector.Core.DTOs.SavedSearches;

public class SavedSearchFilterCriteria
{
    public List<string>? SetAsideCodes { get; set; }
    public List<string>? NaicsCodes { get; set; }
    public List<string>? States { get; set; }
    public decimal? MinAwardAmount { get; set; }
    public decimal? MaxAwardAmount { get; set; }
    public bool OpenOnly { get; set; } = true;
    public List<string>? Types { get; set; }
    public int? DaysBack { get; set; }
}
