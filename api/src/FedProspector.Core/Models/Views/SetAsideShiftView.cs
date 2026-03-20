namespace FedProspector.Core.Models.Views;

public class SetAsideShiftView
{
    public string NoticeId { get; set; } = string.Empty;
    public string? SolicitationNumber { get; set; }
    public string? CurrentSetAsideCode { get; set; }
    public string? CurrentSetAsideDescription { get; set; }
    public string? PredecessorSetAsideType { get; set; }
    public string? PredecessorVendorName { get; set; }
    public string? PredecessorVendorUei { get; set; }
    public DateOnly? PredecessorDateSigned { get; set; }
    public decimal? PredecessorValue { get; set; }
    public bool? ShiftDetected { get; set; }
}
