using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models.Views;

public class PortfolioGapAnalysisView
{
    [Column("organization_id")]
    public int OrganizationId { get; set; }

    [Column("naics_code")]
    public string NaicsCode { get; set; } = string.Empty;

    [Column("opportunity_count")]
    public int OpportunityCount { get; set; }

    [Column("past_performance_count")]
    public int PastPerformanceCount { get; set; }

    [Column("gap_type")]
    public string GapType { get; set; } = string.Empty;
}
