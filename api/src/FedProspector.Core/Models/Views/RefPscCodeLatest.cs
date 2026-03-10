namespace FedProspector.Core.Models.Views;

/// <summary>
/// Read-only view returning the latest PSC name for each PSC code.
/// Mapped to the ref_psc_code_latest database view (keyless).
/// </summary>
public class RefPscCodeLatest
{
    public string PscCode { get; set; } = string.Empty;
    public string? PscName { get; set; }
}
