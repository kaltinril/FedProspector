namespace FedProspector.Core.DTOs.Onboarding;

public class PastPerformanceRelevanceDto
{
    public int PastPerformanceId { get; set; }
    public string? ContractNumber { get; set; }
    public string? PpAgency { get; set; }
    public string? PpNaics { get; set; }
    public decimal? PpValue { get; set; }
    public string NoticeId { get; set; } = string.Empty;
    public string? OpportunityTitle { get; set; }
    public string? OppAgency { get; set; }
    public string? OppNaics { get; set; }
    public decimal? OppValue { get; set; }
    public bool NaicsMatch { get; set; }
    public bool AgencyMatch { get; set; }
    public decimal? ValueSimilarity { get; set; }
    public decimal? YearsSinceCompletion { get; set; }
    public decimal? RelevanceScore { get; set; }
}
