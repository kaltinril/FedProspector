namespace FedProspector.Core.DTOs.Proposals;

public class ProposalDetailDto
{
    public int ProposalId { get; set; }
    public int ProspectId { get; set; }
    public string? ProposalNumber { get; set; }
    public string ProposalStatus { get; set; } = string.Empty;
    public DateTime? SubmissionDeadline { get; set; }
    public DateTime? SubmittedAt { get; set; }
    public decimal? EstimatedValue { get; set; }
    public decimal? WinProbabilityPct { get; set; }
    public string? LessonsLearned { get; set; }
    public List<ProposalMilestoneDto> Milestones { get; set; } = [];
    public List<ProposalDocumentDto> Documents { get; set; } = [];
    public DateTime? CreatedAt { get; set; }
    public DateTime? UpdatedAt { get; set; }
}
