namespace FedProspector.Core.DTOs.Prospects;

public class ProspectProposalSummaryDto
{
    public int ProposalId { get; set; }
    public string ProposalStatus { get; set; } = string.Empty;
    public DateTime? SubmissionDeadline { get; set; }
    public DateTime? SubmittedAt { get; set; }
    public decimal? EstimatedValue { get; set; }
}
