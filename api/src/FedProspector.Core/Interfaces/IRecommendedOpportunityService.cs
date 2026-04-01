using FedProspector.Core.DTOs.Intelligence;

namespace FedProspector.Core.Interfaces;

public interface IRecommendedOpportunityService
{
    Task<List<RecommendedOpportunityDto>> GetRecommendedAsync(int orgId, int limit = 10);

    /// <summary>
    /// Calculate OQS for a single opportunity against the org's profile.
    /// </summary>
    Task<RecommendedOpportunityDto?> CalculateOqScoreAsync(string noticeId, int orgId);
}
