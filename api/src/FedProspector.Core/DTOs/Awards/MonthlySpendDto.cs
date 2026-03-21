using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.DTOs.Awards;

public class MonthlySpendDto
{
    [Column("year_month")]
    public string YearMonth { get; set; } = string.Empty;

    [Column("amount")]
    public decimal Amount { get; set; }

    [Column("transaction_count")]
    public int TransactionCount { get; set; }
}
