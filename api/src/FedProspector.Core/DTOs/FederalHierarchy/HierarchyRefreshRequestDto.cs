namespace FedProspector.Core.DTOs.FederalHierarchy;

public class HierarchyRefreshRequestDto
{
    /// <summary>
    /// Refresh level: "hierarchy" (levels 1-2), "offices" (level 3), or "full" (all).
    /// </summary>
    public string Level { get; set; } = "hierarchy";

    /// <summary>
    /// SAM.gov API key to use: 1 or 2.
    /// </summary>
    public int ApiKey { get; set; } = 2;
}
