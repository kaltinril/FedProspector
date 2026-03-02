namespace FedProspector.Core.DTOs.Prospects;

public class ScoreCriterionDto
{
    public int Score { get; set; }
    public int Max { get; set; }
    public string Detail { get; set; } = string.Empty;
}
