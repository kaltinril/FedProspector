using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models.Views;

public class AgencyRecompetePatternView
{
    [Column("contracting_office_id")]
    public string ContractingOfficeId { get; set; } = string.Empty;

    [Column("contracting_office_name")]
    public string? ContractingOfficeName { get; set; }

    [Column("agency_name")]
    public string? AgencyName { get; set; }

    [Column("incumbent_retention_rate_pct")]
    public decimal? IncumbentRetentionRatePct { get; set; }

    [Column("new_entrant_win_rate_pct")]
    public decimal? NewEntrantWinRatePct { get; set; }

    [Column("set_aside_shift_frequency_pct")]
    public decimal? SetAsideShiftFrequencyPct { get; set; }

    [Column("avg_solicitation_lead_time_days")]
    public decimal? AvgSolicitationLeadTimeDays { get; set; }

    [Column("bridge_extension_frequency_pct")]
    public decimal? BridgeExtensionFrequencyPct { get; set; }

    [Column("sole_source_rate_pct")]
    public decimal? SoleSourceRatePct { get; set; }

    [Column("naics_shift_rate_pct")]
    public decimal? NaicsShiftRatePct { get; set; }

    [Column("total_contracts_analyzed")]
    public int TotalContractsAnalyzed { get; set; }
}
