using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models.Views;

public class PartnerRiskAssessmentView
{
    [Column("uei_sam")]
    public string UeiSam { get; set; } = string.Empty;

    [Column("legal_business_name")]
    public string? LegalBusinessName { get; set; }

    [Column("current_exclusion_flag")]
    public int CurrentExclusionFlag { get; set; }

    [Column("exclusion_count")]
    public int ExclusionCount { get; set; }

    [Column("termination_for_cause_count")]
    public int TerminationForCauseCount { get; set; }

    [Column("spending_trajectory")]
    public string? SpendingTrajectory { get; set; }

    [Column("recent_2yr_value")]
    public decimal Recent2yrValue { get; set; }

    [Column("prior_2yr_value")]
    public decimal Prior2yrValue { get; set; }

    [Column("top_agency_name")]
    public string? TopAgencyName { get; set; }

    [Column("customer_concentration_pct")]
    public decimal CustomerConcentrationPct { get; set; }

    [Column("certification_count")]
    public int CertificationCount { get; set; }

    [Column("total_contract_value")]
    public decimal TotalContractValue { get; set; }

    [Column("years_in_business")]
    public decimal? YearsInBusiness { get; set; }
}
