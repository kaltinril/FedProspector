using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models.Views;

public class AgencyBuyingPatternView
{
    [Column("agency_id")]
    public string AgencyId { get; set; } = string.Empty;

    [Column("agency_name")]
    public string? AgencyName { get; set; }

    [Column("award_year")]
    public int AwardYear { get; set; }

    [Column("award_quarter")]
    public int AwardQuarter { get; set; }

    [Column("contract_count")]
    public int ContractCount { get; set; }

    [Column("total_obligated")]
    public decimal? TotalObligated { get; set; }

    // Set-aside percentages
    [Column("small_business_pct")]
    public decimal? SmallBusinessPct { get; set; }

    [Column("wosb_pct")]
    public decimal? WosbPct { get; set; }

    [Column("eight_a_pct")]
    public decimal? EightAPct { get; set; }

    [Column("hubzone_pct")]
    public decimal? HubzonePct { get; set; }

    [Column("sdvosb_pct")]
    public decimal? SdvosbPct { get; set; }

    [Column("unrestricted_pct")]
    public decimal? UnrestrictedPct { get; set; }

    // Competition percentages
    [Column("full_competition_pct")]
    public decimal? FullCompetitionPct { get; set; }

    [Column("sole_source_pct")]
    public decimal? SoleSourcePct { get; set; }

    [Column("limited_competition_pct")]
    public decimal? LimitedCompetitionPct { get; set; }

    // Contract type percentages
    [Column("ffp_pct")]
    public decimal? FfpPct { get; set; }

    [Column("tm_pct")]
    public decimal? TmPct { get; set; }

    [Column("cost_plus_pct")]
    public decimal? CostPlusPct { get; set; }

    [Column("other_type_pct")]
    public decimal? OtherTypePct { get; set; }

    // Raw counts
    [Column("small_business_count")]
    public int SmallBusinessCount { get; set; }

    [Column("wosb_count")]
    public int WosbCount { get; set; }

    [Column("eight_a_count")]
    public int EightACount { get; set; }

    [Column("hubzone_count")]
    public int HubzoneCount { get; set; }

    [Column("sdvosb_count")]
    public int SdvosbCount { get; set; }

    [Column("unrestricted_count")]
    public int UnrestrictedCount { get; set; }

    [Column("full_competition_count")]
    public int FullCompetitionCount { get; set; }

    [Column("sole_source_count")]
    public int SoleSourceCount { get; set; }

    [Column("limited_competition_count")]
    public int LimitedCompetitionCount { get; set; }

    [Column("ffp_count")]
    public int FfpCount { get; set; }

    [Column("tm_count")]
    public int TmCount { get; set; }

    [Column("cost_plus_count")]
    public int CostPlusCount { get; set; }

    [Column("other_type_count")]
    public int OtherTypeCount { get; set; }
}
