namespace FedProspector.Core.DTOs.Organizations;

public class NaicsDetailDto
{
    public string Code { get; set; } = string.Empty;
    public string Title { get; set; } = string.Empty;
    public decimal? SizeStandard { get; set; }
    public string? SizeType { get; set; }
    public string? IndustryDescription { get; set; }

    /// <summary>
    /// SBA size-standard footnotes/exceptions applicable to this NAICS code.
    /// Empty when the code has no associated footnote_id. (Phase 129 Unit F)
    /// </summary>
    public List<NaicsFootnoteDto> Footnotes { get; set; } = new();
}
