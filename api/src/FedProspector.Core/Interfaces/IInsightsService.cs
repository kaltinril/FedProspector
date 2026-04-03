using FedProspector.Core.DTOs.Insights;

namespace FedProspector.Core.Interfaces;

public interface IInsightsService
{
    Task<List<SimilarOpportunityDto>> GetSimilarOpportunitiesAsync(string noticeId, int maxResults = 20);
    Task<List<CrossSourceValidationDto>> GetCrossSourceValidationAsync();
    Task<List<DataFreshnessDto>> GetDataFreshnessAsync();
    Task<List<DataCompletenessDto>> GetDataCompletenessAsync();
    Task<DataQualityDashboardDto> GetDataQualityDashboardAsync();
    Task<List<ProspectCompetitorSummaryDto>> GetProspectCompetitorSummariesAsync(int organizationId, int[] prospectIds);
    Task<ProspectCompetitorSummaryDto?> GetProspectCompetitorSummaryAsync(int prospectId);
}
