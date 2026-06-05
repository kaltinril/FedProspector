namespace FedProspector.Core.DTOs.Organizations;

public class OrganizationEntityDto
{
    public int Id { get; set; }
    public string UeiSam { get; set; } = string.Empty;
    public string? PartnerUei { get; set; }
    public string Relationship { get; set; } = string.Empty;
    public bool IsActive { get; set; }
    public string? Notes { get; set; }
    public string? AddedByName { get; set; }
    public DateTime CreatedAt { get; set; }

    // Phase 133 Task 6: owner-entered affiliate financials + approved-MPA flag (per link).
    public decimal? AffiliateAnnualRevenue { get; set; }
    public int? AffiliateEmployeeCount { get; set; }
    public bool MpaApproved { get; set; }
    public DateOnly? MpaEffectiveDate { get; set; }

    // Entity details
    public string? LegalBusinessName { get; set; }
    public string? DbaName { get; set; }
    public string? CageCode { get; set; }
    public string? RegistrationStatus { get; set; }
    public string? PrimaryNaics { get; set; }
    public int NaicsCount { get; set; }
    public int CertificationCount { get; set; }
}

public class LinkEntityRequest
{
    public string UeiSam { get; set; } = string.Empty;
    public string? PartnerUei { get; set; }
    public string Relationship { get; set; } = "SELF";
    public string? Notes { get; set; }

    // Phase 133 Task 6: owner-entered affiliate financials + approved-MPA flag (per link).
    public decimal? AffiliateAnnualRevenue { get; set; }
    public int? AffiliateEmployeeCount { get; set; }
    public bool? MpaApproved { get; set; }
    public DateOnly? MpaEffectiveDate { get; set; }
}

public class RefreshSelfEntityResponse
{
    public int NaicsCopied { get; set; }
    public int CertificationsCopied { get; set; }
    public bool ProfileUpdated { get; set; }
    public string Message { get; set; } = string.Empty;
}

/// <summary>
/// Phase 136 Unit F: update an EXISTING linked entity's editable data at any time
/// (decoupled from the link/upsert action). Backs PUT /api/v1/org/entities/{linkId}.
/// All fields are optional/null-coalescing — only supplied values are written, so a
/// caller can fix just the affiliate revenue without disturbing the rest of the link.
/// </summary>
public class UpdateEntityLinkRequest
{
    /// <summary>Owner-entered affiliate annual receipts (raw USD). Null leaves the existing value.</summary>
    public decimal? AffiliateAnnualRevenue { get; set; }

    /// <summary>Owner-entered affiliate employee count. Null leaves the existing value.</summary>
    public int? AffiliateEmployeeCount { get; set; }

    /// <summary>SBA-approved mentor-protégé agreement flag (JV_PARTNER only). Null leaves the existing value.</summary>
    public bool? MpaApproved { get; set; }

    /// <summary>Effective date of the approved mentor-protégé agreement. Null leaves the existing value.</summary>
    public DateOnly? MpaEffectiveDate { get; set; }

    /// <summary>Free-text notes. Null leaves the existing value.</summary>
    public string? Notes { get; set; }

    /// <summary>UEI used for JV partnership filings. Null leaves the existing value.</summary>
    public string? PartnerUei { get; set; }
}
