using FedProspector.Core.DTOs;
using FedProspector.Core.DTOs.Awards;

namespace FedProspector.Core.Interfaces;

public interface IAwardService
{
    Task<PagedResponse<AwardSearchDto>> SearchAsync(AwardSearchRequest request);
    Task<AwardDetailResponse> GetDetailAsync(string contractId);
    Task<BurnRateDto?> GetBurnRateAsync(string contractId);
    Task<List<MarketShareDto>> GetMarketShareAsync(string naicsCode, int limit = 10);
    Task<LoadRequestStatusDto> RequestLoadAsync(string contractId, string tier, int? userId);
    Task<LoadRequestStatusDto?> GetLoadStatusAsync(string contractId);
}
