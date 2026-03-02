using FedProspector.Core.DTOs.Proposals;

namespace FedProspector.Core.Interfaces;

public interface IProposalService
{
    Task<ProposalDetailDto> CreateAsync(int userId, CreateProposalRequest request);
    Task<ProposalDetailDto> UpdateAsync(int proposalId, int userId, UpdateProposalRequest request);
    Task<ProposalDocumentDto> AddDocumentAsync(int proposalId, int userId, AddProposalDocumentRequest request);
    Task<IEnumerable<ProposalMilestoneDto>> GetMilestonesAsync(int proposalId);
    Task<ProposalMilestoneDto> UpdateMilestoneAsync(int proposalId, int milestoneId, int userId, UpdateMilestoneRequest request);
}
