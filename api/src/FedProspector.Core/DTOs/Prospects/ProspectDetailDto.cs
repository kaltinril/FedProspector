namespace FedProspector.Core.DTOs.Prospects;

public class ProspectDetailDto
{
    public ProspectSummaryDto Prospect { get; set; } = new();
    public ProspectOpportunityDto? Opportunity { get; set; }
    public List<ProspectNoteDto> Notes { get; set; } = [];
    public List<ProspectTeamMemberDto> TeamMembers { get; set; } = [];
    public ProspectProposalSummaryDto? Proposal { get; set; }
    public ScoreBreakdownDto? ScoreBreakdown { get; set; }
}
