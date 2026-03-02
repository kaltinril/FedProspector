using FedProspector.Core.DTOs;
using FedProspector.Core.DTOs.Prospects;

namespace FedProspector.Core.Interfaces;

public interface IProspectService
{
    Task<ProspectDetailDto> CreateAsync(int userId, CreateProspectRequest request);
    Task<PagedResponse<ProspectListDto>> SearchAsync(ProspectSearchRequest request);
    Task<ProspectDetailDto?> GetDetailAsync(int prospectId);
    Task<ProspectDetailDto> UpdateStatusAsync(int prospectId, int userId, UpdateProspectStatusRequest request);
    Task<ProspectDetailDto> ReassignAsync(int prospectId, int userId, ReassignProspectRequest request);
    Task<ProspectNoteDto> AddNoteAsync(int prospectId, int userId, CreateProspectNoteRequest request);
    Task<ProspectTeamMemberDto> AddTeamMemberAsync(int prospectId, int userId, AddTeamMemberRequest request);
    Task<bool> RemoveTeamMemberAsync(int prospectId, int memberId, int userId);
    Task<ScoreBreakdownDto> RecalculateScoreAsync(int prospectId, int userId);
}
