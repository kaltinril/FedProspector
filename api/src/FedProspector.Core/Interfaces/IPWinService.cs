using FedProspector.Core.DTOs.Intelligence;

namespace FedProspector.Core.Interfaces;

public interface IPWinService
{
    Task<PWinResultDto> CalculateAsync(string noticeId, int orgId);
    Task<BatchPWinResponse> CalculateBatchAsync(BatchPWinRequest request, int orgId);
}
