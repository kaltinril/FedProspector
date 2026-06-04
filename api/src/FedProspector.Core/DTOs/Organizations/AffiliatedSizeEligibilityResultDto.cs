namespace FedProspector.Core.DTOs.Organizations;

/// <summary>
/// Result of an affiliation-aware SBA size determination (Phase 133 Task 6, 13 CFR 121.103).
/// Reports BOTH the standalone (org-only) verdict and the rolled-up verdict that combines the
/// org's own receipts/headcount with each included affiliate's. The included affiliation set is
/// active links with relationship in { SELF, SISTER_SUBSIDIARY, JV_PARTNER }; TEAMING is excluded,
/// and a JV_PARTNER flagged as an approved mentor-protégé agreement (mpa_approved = 'Y') is excluded
/// (the mentor's size is not counted). Missing affiliate figures are reported as gaps, NOT treated as zero.
/// </summary>
public class AffiliatedSizeEligibilityResultDto
{
    public string NaicsCode { get; set; } = string.Empty;

    /// <summary>SBA size standard type: "M" = annual receipts (USD millions), "E" = employees. Null when no standard found.</summary>
    public string? SizeType { get; set; }

    /// <summary>The NAICS size-standard threshold (USD millions for "M", employee count for "E"). Null when no standard found.</summary>
    public decimal? Threshold { get; set; }

    /// <summary>True = small/eligible, false = not small, null = cannot determine — based on the ORG ALONE.</summary>
    public bool? StandaloneEligible { get; set; }

    /// <summary>True = small/eligible, false = not small, null = cannot determine — based on the COMBINED (org + included affiliates) total.</summary>
    public bool? AffiliatedEligible { get; set; }

    /// <summary>Combined annual receipts in USD millions (org + included affiliates). Null for employee-based ("E") standards or when undeterminable.</summary>
    public decimal? CombinedRevenue { get; set; }

    /// <summary>Combined employee count (org + included affiliates). Null for receipts-based ("M") standards or when undeterminable.</summary>
    public decimal? CombinedEmployees { get; set; }

    /// <summary>Count of affiliate links included in the roll-up (excludes the org's own SELF row and excluded links).</summary>
    public int AffiliateCount { get; set; }

    /// <summary>Affiliates whose figures were included in the combined total.</summary>
    public List<IncludedAffiliateDto> IncludedAffiliates { get; set; } = new();

    /// <summary>Affiliates deliberately excluded from the roll-up, with the reason (APPROVED_MPA or TEAMING).</summary>
    public List<ExcludedAffiliateDto> ExcludedAffiliates { get; set; } = new();

    /// <summary>UEIs of included affiliates missing the figure needed for this size_type (a gap; NOT treated as zero).</summary>
    public List<string> MissingAffiliateData { get; set; } = new();

    /// <summary>True when the org is small standalone but the combined enterprise is other-than-small — the dangerous case.</summary>
    public bool FlippedToOtherThanSmall { get; set; }

    /// <summary>Short human-readable explanation of the affiliated determination.</summary>
    public string Reason { get; set; } = string.Empty;
}

/// <summary>An affiliate counted in the size roll-up, with the amount it contributed for the applicable size_type.</summary>
public class IncludedAffiliateDto
{
    public string Uei { get; set; } = string.Empty;
    public string Relationship { get; set; } = string.Empty;

    /// <summary>Contribution in the comparison unit: USD millions for "M", employee count for "E". Null when this affiliate's figure is missing (a gap).</summary>
    public decimal? ContributedAmount { get; set; }
}

/// <summary>An affiliate excluded from the size roll-up, with the exclusion reason.</summary>
public class ExcludedAffiliateDto
{
    public string Uei { get; set; } = string.Empty;
    public string Relationship { get; set; } = string.Empty;

    /// <summary>"APPROVED_MPA" (flagged mentor-protégé JV) or "TEAMING" (teaming partner).</summary>
    public string Reason { get; set; } = string.Empty;
}
