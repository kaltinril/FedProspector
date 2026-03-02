using FedProspector.Core.DTOs;
using FedProspector.Core.DTOs.Awards;

namespace FedProspector.Core.Interfaces;

public interface IAwardService
{
    Task<PagedResponse<AwardSearchDto>> SearchAsync(AwardSearchRequest request);
    Task<AwardDetailDto?> GetDetailAsync(string contractId);
    Task<BurnRateDto?> GetBurnRateAsync(string contractId);
}
