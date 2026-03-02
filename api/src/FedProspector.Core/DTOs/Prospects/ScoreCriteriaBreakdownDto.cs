namespace FedProspector.Core.DTOs.Prospects;

public class ScoreCriteriaBreakdownDto
{
    public ScoreCriterionDto SetAside { get; set; } = new();
    public ScoreCriterionDto TimeRemaining { get; set; } = new();
    public ScoreCriterionDto NaicsMatch { get; set; } = new();
    public ScoreCriterionDto AwardValue { get; set; } = new();
}
