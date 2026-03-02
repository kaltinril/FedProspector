namespace FedProspector.Core.DTOs.Prospects;

public class ScoreBreakdownDto
{
    public int ProspectId { get; set; }
    public int TotalScore { get; set; }
    public int MaxScore { get; set; }
    public decimal Percentage { get; set; }
    public ScoreCriteriaBreakdownDto Breakdown { get; set; } = new();
}
