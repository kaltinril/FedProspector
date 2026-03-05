namespace FedProspector.Core.DTOs.Organizations;

public class NaicsDetailDto
{
    public string Code { get; set; } = string.Empty;
    public string Title { get; set; } = string.Empty;
    public decimal? SizeStandard { get; set; }
    public string? SizeType { get; set; }
    public string? IndustryDescription { get; set; }
}
