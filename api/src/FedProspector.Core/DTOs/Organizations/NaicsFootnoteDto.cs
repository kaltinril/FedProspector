namespace FedProspector.Core.DTOs.Organizations;

/// <summary>
/// A single SBA size-standard footnote/exception entry for a NAICS code.
/// Sourced from ref_naics_footnote (composite key footnote_id + section).
/// </summary>
public class NaicsFootnoteDto
{
    public string FootnoteId { get; set; } = string.Empty;
    public string Section { get; set; } = string.Empty;
    public string Description { get; set; } = string.Empty;
}
