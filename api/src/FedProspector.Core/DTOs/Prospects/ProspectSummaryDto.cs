namespace FedProspector.Core.DTOs.Prospects;

public class ProspectSummaryDto
{
    public int ProspectId { get; set; }
    public string NoticeId { get; set; } = string.Empty;
    public string Status { get; set; } = string.Empty;
    public string? Priority { get; set; }
    public decimal? GoNoGoScore { get; set; }
    public decimal? WinProbability { get; set; }
    public decimal? EstimatedValue { get; set; }
    public decimal? EstimatedGrossMarginPct { get; set; }
    public DateOnly? BidSubmittedDate { get; set; }
    public string? Outcome { get; set; }
    public DateOnly? OutcomeDate { get; set; }
    public string? OutcomeNotes { get; set; }
    public UserSummaryDto? CaptureManager { get; set; }
    public UserSummaryDto? AssignedTo { get; set; }
    public DateTime? CreatedAt { get; set; }
    public DateTime? UpdatedAt { get; set; }
}
