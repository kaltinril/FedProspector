namespace FedProspector.Core.DTOs.Proposals;

public class UpdateProposalRequest
{
    public string? Status { get; set; }
    public decimal? EstimatedValue { get; set; }
    public decimal? WinProbabilityPct { get; set; }
    public string? Notes { get; set; }
}
