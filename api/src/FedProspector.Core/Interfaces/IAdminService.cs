using FedProspector.Core.DTOs.Admin;

namespace FedProspector.Core.Interfaces;

public interface IAdminService
{
    Task<EtlStatusDto> GetEtlStatusAsync();
    Task<List<UserListDto>> GetUsersAsync();
    Task<UserListDto> UpdateUserAsync(int userId, UpdateUserRequest request, int adminUserId);
    Task<ResetPasswordResponse> ResetPasswordAsync(int userId, int adminUserId);
}
