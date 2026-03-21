using System.ComponentModel.DataAnnotations.Schema;

namespace FedProspector.Core.Models.Views;

public class MonthlySpendView
{
    [Column("award_id")]
    public string AwardId { get; set; } = string.Empty;

    [Column("year_month")]
    public string YearMonth { get; set; } = string.Empty;

    [Column("amount")]
    public decimal Amount { get; set; }

    [Column("transaction_count")]
    public int TransactionCount { get; set; }
}
