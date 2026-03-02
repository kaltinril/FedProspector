namespace FedProspector.Core.DTOs.Awards;

public class MonthlySpendDto
{
    public string YearMonth { get; set; } = string.Empty;
    public decimal Amount { get; set; }
    public int TransactionCount { get; set; }
}
