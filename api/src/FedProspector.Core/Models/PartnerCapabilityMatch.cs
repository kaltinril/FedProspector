using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models;

/// <summary>
/// Daily-refreshed materialization of v_partner_capability_match.
/// Backs the Teaming Partner Search and Gap Analysis tabs so they read flat,
/// pre-aggregated rows instead of scanning the >90s view per request.
/// Populated by `refresh partner-capability` (etl_utils.refresh_partner_capability_match).
/// </summary>
[Table("partner_capability_match")]
public class PartnerCapabilityMatch
{
    [Column("uei_sam")]
    public string UeiSam { get; set; } = string.Empty;

    [Column("legal_business_name")]
    public string? LegalBusinessName { get; set; }

    [Column("state")]
    public string? State { get; set; }

    [Column("naics_codes")]
    public string? NaicsCodes { get; set; }

    [Column("psc_codes")]
    public string? PscCodes { get; set; }

    [Column("certifications")]
    public string? Certifications { get; set; }

    [Column("agencies_worked_with")]
    public string? AgenciesWorkedWith { get; set; }

    [Column("performance_naics_codes")]
    public string? PerformanceNaicsCodes { get; set; }

    [Column("contract_count")]
    public int ContractCount { get; set; }

    [Column("total_contract_value")]
    public decimal TotalContractValue { get; set; }

    [Column("computed_at")]
    public DateTime ComputedAt { get; set; }
}
