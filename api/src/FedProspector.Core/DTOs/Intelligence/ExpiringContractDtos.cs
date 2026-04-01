namespace FedProspector.Core.DTOs.Intelligence;

public class ExpiringContractDto
{
    public string Piid { get; set; } = "";
    public string? Description { get; set; }
    public string? NaicsCode { get; set; }
    public string? SetAsideType { get; set; }
    public string? VendorUei { get; set; }
    public string? VendorName { get; set; }
    public string? AgencyName { get; set; }
    public string? OfficeName { get; set; }
    public decimal? ContractValue { get; set; }
    public decimal? DollarsObligated { get; set; }
    public DateTime? CompletionDate { get; set; }
    public DateTime? DateSigned { get; set; }
    public int? MonthsRemaining { get; set; }
    // Incumbent health
    public string? RegistrationStatus { get; set; }
    public DateTime? RegistrationExpiration { get; set; }
    // Burn rate
    public decimal? MonthlyBurnRate { get; set; }
    public decimal? PercentSpent { get; set; }
    // Re-solicitation status
    public string? ResolicitationNoticeId { get; set; }
    public string ResolicitationStatus { get; set; } = "Not Yet Posted";
    // Set-aside shift (enriched from v_set_aside_shift)
    public string? PredecessorSetAsideType { get; set; }
    public bool? ShiftDetected { get; set; }
    // Data source (Phase 127)
    public string Source { get; set; } = "FPDS";
}

public class ExpiringContractSearchRequest
{
    public int MonthsAhead { get; set; } = 12;
    public string? NaicsCode { get; set; }
    public string? SetAsideType { get; set; }
    public string? Agency { get; set; }
    public string? Piid { get; set; }
    public string? VendorName { get; set; }
    public bool OnlyMyNaics { get; set; } = true;
    public int Limit { get; set; } = 50;
    public int Offset { get; set; } = 0;
}
