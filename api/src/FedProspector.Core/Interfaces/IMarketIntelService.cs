using FedProspector.Core.DTOs.Intelligence;

namespace FedProspector.Core.Interfaces;

public interface IMarketIntelService
{
    Task<MarketShareAnalysisDto> GetMarketShareAsync(string naicsCode, int years = 3, int limit = 10);
    Task<IncumbentAnalysisDto> GetIncumbentAnalysisAsync(string noticeId);
}
