namespace FedProspector.Core.DTOs.Pipeline;

public class RevenueForecastDto
{
    public string ForecastMonth { get; set; } = string.Empty;
    public int ProspectCount { get; set; }
    public decimal? TotalUnweightedValue { get; set; }
    public decimal? TotalWeightedValue { get; set; }
    public decimal? AvgWinProbability { get; set; }
}
