using FedProspector.Core.DTOs;
using FedProspector.Core.DTOs.Admin;

namespace FedProspector.Core.Interfaces;

public interface IAdminService
{
    Task<EtlStatusDto> GetEtlStatusAsync();
    Task<PagedResponse<UserListDto>> GetUsersAsync(int organizationId, int page = 1, int pageSize = 25);
    Task<UserListDto> UpdateUserAsync(int userId, UpdateUserRequest request, int adminUserId, int adminOrgId);
    Task<ResetPasswordResponse> ResetPasswordAsync(int userId, int adminUserId, int adminOrgId);
    Task<LoadHistoryResponse> GetLoadHistoryAsync(string? source, string? status, int days, int limit, int offset);
    Task<List<HealthSnapshotDto>> GetHealthSnapshotsAsync(int days);
    Task<List<ApiKeyStatusDto>> GetApiKeyStatusAsync();
    Task<List<JobStatusDto>> GetJobStatusAsync();
}
