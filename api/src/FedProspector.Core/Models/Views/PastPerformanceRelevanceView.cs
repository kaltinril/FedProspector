using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models.Views;

public class PastPerformanceRelevanceView
{
    [Column("organization_id")]
    public int OrganizationId { get; set; }

    [Column("past_performance_id")]
    public int PastPerformanceId { get; set; }

    [Column("contract_number")]
    public string? ContractNumber { get; set; }

    [Column("pp_agency")]
    public string? PpAgency { get; set; }

    [Column("pp_naics")]
    public string? PpNaics { get; set; }

    [Column("pp_value")]
    public decimal? PpValue { get; set; }

    [Column("notice_id")]
    public string NoticeId { get; set; } = string.Empty;

    [Column("opportunity_title")]
    public string? OpportunityTitle { get; set; }

    [Column("opp_agency")]
    public string? OppAgency { get; set; }

    [Column("opp_naics")]
    public string? OppNaics { get; set; }

    [Column("opp_value")]
    public decimal? OppValue { get; set; }

    [Column("naics_match")]
    public bool NaicsMatch { get; set; }

    [Column("agency_match")]
    public bool AgencyMatch { get; set; }

    [Column("value_similarity")]
    public decimal? ValueSimilarity { get; set; }

    [Column("years_since_completion")]
    public decimal? YearsSinceCompletion { get; set; }

    [Column("relevance_score")]
    public decimal? RelevanceScore { get; set; }
}
