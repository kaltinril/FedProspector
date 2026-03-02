using FedProspector.Core.DTOs;
using FedProspector.Core.DTOs.Prospects;

namespace FedProspector.Core.Interfaces;

public interface IProspectService
{
    Task<ProspectDetailDto> CreateAsync(int userId, int organizationId, CreateProspectRequest request);
    Task<PagedResponse<ProspectListDto>> SearchAsync(int organizationId, ProspectSearchRequest request);
    Task<ProspectDetailDto?> GetDetailAsync(int organizationId, int prospectId);
    Task<ProspectDetailDto> UpdateStatusAsync(int organizationId, int prospectId, int userId, UpdateProspectStatusRequest request);
    Task<ProspectDetailDto> ReassignAsync(int organizationId, int prospectId, int userId, ReassignProspectRequest request);
    Task<ProspectNoteDto> AddNoteAsync(int organizationId, int prospectId, int userId, CreateProspectNoteRequest request);
    Task<ProspectTeamMemberDto> AddTeamMemberAsync(int organizationId, int prospectId, int userId, AddTeamMemberRequest request);
    Task<bool> RemoveTeamMemberAsync(int organizationId, int prospectId, int memberId, int userId);
    Task<ScoreBreakdownDto> RecalculateScoreAsync(int organizationId, int prospectId, int userId);
}
