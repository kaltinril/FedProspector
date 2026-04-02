namespace FedProspector.Core.DTOs.Pricing;

public class CanonicalCategoryDto
{
    public int Id { get; set; }
    public string Name { get; set; } = "";
    public string? Group { get; set; }
    public string? OnetCode { get; set; }
    public string? Description { get; set; }
}

public class LaborCategorySearchResult
{
    public int Id { get; set; }
    public string Name { get; set; } = "";
    public string? Group { get; set; }
    public string? OnetCode { get; set; }
    public string? Description { get; set; }
    public int MatchCount { get; set; }
}
