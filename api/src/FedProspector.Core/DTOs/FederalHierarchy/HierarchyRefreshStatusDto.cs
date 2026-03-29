namespace FedProspector.Core.DTOs.FederalHierarchy;

public class HierarchyRefreshStatusDto
{
    public bool IsRunning { get; set; }
    public DateTime? LastRefreshAt { get; set; }
    public int? LastRefreshRecordCount { get; set; }
    public List<HierarchyLevelCount> LevelsLoaded { get; set; } = [];
    public int? JobId { get; set; }
}

public class HierarchyLevelCount
{
    public int Level { get; set; }
    public int Count { get; set; }
}
