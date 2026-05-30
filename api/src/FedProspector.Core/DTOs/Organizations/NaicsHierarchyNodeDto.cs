namespace FedProspector.Core.DTOs.Organizations;

/// <summary>
/// A node in the NAICS classification hierarchy. Used for sector/children/ancestor
/// browsing (breadcrumbs and drill-down). Level follows the NAICS digit count
/// (2 = sector, 6 = national industry / leaf).
/// </summary>
public class NaicsHierarchyNodeDto
{
    public string Code { get; set; } = string.Empty;
    public string Title { get; set; } = string.Empty;
    public byte? Level { get; set; }
    public string? LevelName { get; set; }
    public string? ParentCode { get; set; }

    /// <summary>True when this is a 6-digit national industry code (no further children).</summary>
    public bool IsLeaf { get; set; }
}
