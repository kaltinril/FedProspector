namespace FedProspector.Core.DTOs.Proposals;

public class UpdateProposalRequest
{
    public string? Status { get; set; }
    public decimal? EstimatedValue { get; set; }
    public decimal? WinProbabilityPct { get; set; }
    // Fix 12: Notes field removed. Proposals do not have a dedicated notes table.
    // To record notes on a proposal, add a note to the associated prospect via
    // POST /api/v1/prospects/{id}/notes instead.
    public string? LessonsLearned { get; set; }
}
