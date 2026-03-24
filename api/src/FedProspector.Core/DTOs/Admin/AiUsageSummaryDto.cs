namespace FedProspector.Core.DTOs.Admin;

public class AiUsageSummaryDto
{
    public string Period { get; set; } = string.Empty;
    public decimal TotalCostUsd { get; set; }
    public long TotalInputTokens { get; set; }
    public long TotalOutputTokens { get; set; }
    public int TotalRequests { get; set; }
    public int TotalDocuments { get; set; }
    public List<ModelUsageDto> ByModel { get; set; } = [];
    public List<DailyUsageDto> ByDay { get; set; } = [];
}

public class ModelUsageDto
{
    public string Model { get; set; } = string.Empty;
    public decimal CostUsd { get; set; }
    public int Requests { get; set; }
}

public class DailyUsageDto
{
    public string Date { get; set; } = string.Empty;
    public decimal CostUsd { get; set; }
    public int Requests { get; set; }
}
