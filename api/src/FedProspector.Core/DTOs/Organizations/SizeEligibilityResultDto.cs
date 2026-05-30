namespace FedProspector.Core.DTOs.Organizations;

/// <summary>
/// Result of evaluating whether an organization qualifies as "small" under the SBA
/// size standard for a given NAICS code. Side-effect free and safe to call per
/// opportunity. Never throws: missing inputs (no size standard, no org revenue/
/// headcount) yield <see cref="Eligible"/> = null with an explanatory <see cref="Reason"/>.
/// </summary>
public class SizeEligibilityResultDto
{
    public string NaicsCode { get; set; } = string.Empty;

    /// <summary>SBA size standard type: "M" = annual receipts (USD millions), "E" = employees. Null when no standard found.</summary>
    public string? SizeType { get; set; }

    /// <summary>The size standard threshold as stored in ref_sba_size_standard (millions of USD for "M", employee count for "E").</summary>
    public decimal? Threshold { get; set; }

    /// <summary>"USD_MILLIONS" or "EMPLOYEES". Null when no standard found.</summary>
    public string? ThresholdUnit { get; set; }

    /// <summary>The organization's measured value (annual revenue or employee count). Null when the org has not filled it in.</summary>
    public decimal? ActualValue { get; set; }

    /// <summary>True = small/eligible, false = not small, null = cannot determine (missing inputs).</summary>
    public bool? Eligible { get; set; }

    /// <summary>True only when actual value exceeds the threshold (i.e. org is too large). False when unknown.</summary>
    public bool Outsized { get; set; }

    /// <summary>(threshold - actual) / threshold * 100. Positive = room under the cap, negative = over. Null when undeterminable.</summary>
    public decimal? HeadroomPct { get; set; }

    /// <summary>Short human-readable explanation of the result.</summary>
    public string Reason { get; set; } = string.Empty;
}
