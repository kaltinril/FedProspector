namespace FedProspector.Core.DTOs.Intelligence;

public class RecommendedOpportunityDto
{
    public string NoticeId { get; set; } = "";
    public string? Title { get; set; }
    public string? SolicitationNumber { get; set; }
    public string? DepartmentName { get; set; }
    public string? SubTier { get; set; }
    public string? SetAsideCode { get; set; }
    public string? SetAsideDescription { get; set; }
    public string? NaicsCode { get; set; }
    public string? NaicsDescription { get; set; }
    public string? ClassificationCode { get; set; }
    public string? NoticeType { get; set; }
    public decimal? AwardAmount { get; set; }
    public DateTime? PostedDate { get; set; }
    public DateTime? ResponseDeadline { get; set; }
    public int? DaysRemaining { get; set; }
    public string? PopState { get; set; }
    public string? PopCity { get; set; }
    public string? PopCountry { get; set; }
    // Scoring
    public decimal PWinScore { get; set; }
    public string PWinCategory { get; set; } = "";
    // Re-compete indicator
    public bool IsRecompete { get; set; }
    public string? IncumbentName { get; set; }
}
