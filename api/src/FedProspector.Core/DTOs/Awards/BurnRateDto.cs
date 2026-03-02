namespace FedProspector.Core.DTOs.Awards;

public class BurnRateDto
{
    public string ContractId { get; set; } = string.Empty;
    public decimal TotalObligated { get; set; }
    public decimal? BaseAndAllOptions { get; set; }
    public decimal? PercentSpent { get; set; }
    public int MonthsElapsed { get; set; }
    public decimal MonthlyRate { get; set; }
    public int TransactionCount { get; set; }
    public List<MonthlySpendDto> MonthlyBreakdown { get; set; } = [];
}
