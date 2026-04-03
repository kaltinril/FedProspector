using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models.Views;

public class PipelineRevenueForecastView
{
    [Column("organization_id")]
    public int OrganizationId { get; set; }

    [Column("forecast_month")]
    public string ForecastMonth { get; set; } = string.Empty;

    [Column("prospect_count")]
    public int ProspectCount { get; set; }

    [Column("total_unweighted_value")]
    public decimal? TotalUnweightedValue { get; set; }

    [Column("total_weighted_value")]
    public decimal? TotalWeightedValue { get; set; }

    [Column("avg_win_probability")]
    public decimal? AvgWinProbability { get; set; }
}
