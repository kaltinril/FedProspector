namespace FedProspector.Core.DTOs.Pipeline;

public class PipelineFunnelDto
{
    public string Status { get; set; } = string.Empty;
    public int ProspectCount { get; set; }
    public decimal? TotalEstimatedValue { get; set; }
    public decimal? AvgHoursInPriorStatus { get; set; }
    public decimal? WinRatePct { get; set; }
    public int? WonCount { get; set; }
    public int? LostCount { get; set; }
}
