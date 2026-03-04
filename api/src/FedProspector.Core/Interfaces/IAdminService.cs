using FedProspector.Core.DTOs;
using FedProspector.Core.DTOs.Admin;

namespace FedProspector.Core.Interfaces;

public interface IAdminService
{
    Task<EtlStatusDto> GetEtlStatusAsync();
    Task<PagedResponse<UserListDto>> GetUsersAsync(int organizationId, int page = 1, int pageSize = 25);
    Task<UserListDto> UpdateUserAsync(int userId, UpdateUserRequest request, int adminUserId, int adminOrgId);
    Task<ResetPasswordResponse> ResetPasswordAsync(int userId, int adminUserId, int adminOrgId);
}
