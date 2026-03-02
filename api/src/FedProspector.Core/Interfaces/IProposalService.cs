using FedProspector.Core.DTOs;
using FedProspector.Core.DTOs.Proposals;

namespace FedProspector.Core.Interfaces;

public interface IProposalService
{
    Task<ProposalDetailDto> CreateAsync(int userId, int organizationId, CreateProposalRequest request);
    Task<ProposalDetailDto> UpdateAsync(int organizationId, int proposalId, int userId, UpdateProposalRequest request);
    Task<ProposalDocumentDto> AddDocumentAsync(int organizationId, int proposalId, int userId, AddProposalDocumentRequest request);
    Task<IEnumerable<ProposalMilestoneDto>> GetMilestonesAsync(int organizationId, int proposalId);
    Task<ProposalMilestoneDto> UpdateMilestoneAsync(int organizationId, int proposalId, int milestoneId, int userId, UpdateMilestoneRequest request);
    Task<ProposalMilestoneDto> CreateMilestoneAsync(int organizationId, int proposalId, int userId, CreateMilestoneRequest request);
    Task<PagedResponse<ProposalDetailDto>> ListAsync(int organizationId, ProposalSearchRequest request);
}
