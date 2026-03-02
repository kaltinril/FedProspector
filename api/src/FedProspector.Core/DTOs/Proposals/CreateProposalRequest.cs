namespace FedProspector.Core.DTOs.Proposals;

public class CreateProposalRequest
{
    public int ProspectId { get; set; }
    public DateTime? SubmissionDeadline { get; set; }
    public decimal? EstimatedValue { get; set; }
}
