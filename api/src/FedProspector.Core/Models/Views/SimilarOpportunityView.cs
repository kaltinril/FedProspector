using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models.Views;

public class SimilarOpportunityView
{
    [Column("source_notice_id")]
    public string SourceNoticeId { get; set; } = string.Empty;

    [Column("match_notice_id")]
    public string MatchNoticeId { get; set; } = string.Empty;

    [Column("match_title")]
    public string? MatchTitle { get; set; }

    [Column("match_agency")]
    public string? MatchAgency { get; set; }

    [Column("match_naics")]
    public string? MatchNaics { get; set; }

    [Column("match_set_aside")]
    public string? MatchSetAside { get; set; }

    [Column("match_value")]
    public decimal? MatchValue { get; set; }

    [Column("match_posted_date")]
    public DateTime? MatchPostedDate { get; set; }

    [Column("match_response_deadline")]
    public DateTime? MatchResponseDeadline { get; set; }

    [Column("similarity_factors")]
    public string? SimilarityFactors { get; set; }

    [Column("similarity_score")]
    public int SimilarityScore { get; set; }
}
