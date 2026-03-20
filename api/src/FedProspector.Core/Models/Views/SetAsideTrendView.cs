namespace FedProspector.Core.Models.Views;

public class SetAsideTrendView
{
    public string NaicsCode { get; set; } = string.Empty;
    public int FiscalYear { get; set; }
    public string? SetAsideType { get; set; }
    public string? SetAsideCategory { get; set; }
    public int ContractCount { get; set; }
    public decimal TotalValue { get; set; }
    public decimal AvgValue { get; set; }
}
