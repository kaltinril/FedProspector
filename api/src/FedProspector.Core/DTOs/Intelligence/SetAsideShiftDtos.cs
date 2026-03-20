namespace FedProspector.Core.DTOs.Intelligence;

public class SetAsideShiftDto
{
    public string NoticeId { get; set; } = "";
    public string? SolicitationNumber { get; set; }
    public string? CurrentSetAsideCode { get; set; }
    public string? CurrentSetAsideDescription { get; set; }
    public string? PredecessorSetAsideType { get; set; }
    public string? PredecessorVendorName { get; set; }
    public string? PredecessorVendorUei { get; set; }
    public DateTime? PredecessorDateSigned { get; set; }
    public decimal? PredecessorValue { get; set; }
    public bool? ShiftDetected { get; set; }
}

public class SetAsideTrendDto
{
    public string NaicsCode { get; set; } = "";
    public int FiscalYear { get; set; }
    public string? SetAsideType { get; set; }
    public string? SetAsideCategory { get; set; }
    public int ContractCount { get; set; }
    public decimal TotalValue { get; set; }
    public decimal AvgValue { get; set; }
}
