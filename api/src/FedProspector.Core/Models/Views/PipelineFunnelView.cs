using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models.Views;

public class PipelineFunnelView
{
    [Column("organization_id")]
    public int OrganizationId { get; set; }

    [Column("status")]
    public string Status { get; set; } = string.Empty;

    [Column("prospect_count")]
    public int ProspectCount { get; set; }

    [Column("total_estimated_value")]
    public decimal? TotalEstimatedValue { get; set; }

    [Column("avg_hours_in_prior_status")]
    public decimal? AvgHoursInPriorStatus { get; set; }

    [Column("win_rate_pct")]
    public decimal? WinRatePct { get; set; }

    [Column("won_count")]
    public int? WonCount { get; set; }

    [Column("lost_count")]
    public int? LostCount { get; set; }
}
