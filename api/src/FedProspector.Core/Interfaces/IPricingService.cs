using FedProspector.Core.DTOs.Pricing;

namespace FedProspector.Core.Interfaces;

public interface IPricingService
{
    Task<List<CanonicalCategoryDto>> GetCanonicalCategoriesAsync(string? group = null);
    Task<List<CanonicalCategoryDto>> SearchLaborCategoriesAsync(string query);
    Task<List<RateHeatmapCell>> GetRateHeatmapAsync(RateHeatmapRequest request);
    Task<RateDistributionDto> GetRateDistributionAsync(int canonicalId);
    Task<PriceToWinResponse> EstimatePriceToWinAsync(PriceToWinRequest request);
    Task<List<SubBenchmarkDto>> GetSubBenchmarksAsync(SubBenchmarkRequest request);
    Task<List<SubRatioDto>> GetSubRatiosAsync(string? naicsCode);
    Task<List<RateTrendDto>> GetRateTrendsAsync(RateTrendRequest request);
    Task<List<EscalationForecastDto>> GetEscalationForecastAsync(int canonicalId, int years = 5);
    Task<IgceResponse> EstimateIgceAsync(IgceRequest request);
    Task<RateRangeResponse> GetRateRangeAsync(RateRangeRequest request);
    Task<ScaComplianceResponse> CheckScaComplianceAsync(ScaComplianceRequest request);
    Task<List<ScaAreaRateDto>> GetScaAreaRatesAsync(ScaAreaRateRequest request);
    Task<List<string>> GetScaOccupationsAsync();
}
