using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models.Views;

public class ContractingOfficeProfileView
{
    [Column("contracting_office_id")]
    public string ContractingOfficeId { get; set; } = string.Empty;

    [Column("contracting_office_name")]
    public string? ContractingOfficeName { get; set; }

    [Column("agency_name")]
    public string? AgencyName { get; set; }

    [Column("total_awards")]
    public int TotalAwards { get; set; }

    [Column("total_obligated")]
    public decimal? TotalObligated { get; set; }

    [Column("avg_award_value")]
    public decimal? AvgAwardValue { get; set; }

    [Column("earliest_award")]
    public DateOnly? EarliestAward { get; set; }

    [Column("latest_award")]
    public DateOnly? LatestAward { get; set; }

    [Column("top_naics_codes")]
    public string? TopNaicsCodes { get; set; }

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

    [Column("ffp_pct")]
    public decimal? FfpPct { get; set; }

    [Column("tm_pct")]
    public decimal? TmPct { get; set; }

    [Column("cost_plus_pct")]
    public decimal? CostPlusPct { get; set; }

    [Column("full_competition_pct")]
    public decimal? FullCompetitionPct { get; set; }

    [Column("sole_source_pct")]
    public decimal? SoleSourcePct { get; set; }

    [Column("avg_procurement_days")]
    public decimal? AvgProcurementDays { get; set; }
}
