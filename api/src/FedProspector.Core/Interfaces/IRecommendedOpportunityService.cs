using FedProspector.Core.DTOs.Intelligence;

namespace FedProspector.Core.Interfaces;

public interface IRecommendedOpportunityService
{
    /// <summary>
    /// Get scored/ranked recommended opportunities for the org.
    /// </summary>
    /// <param name="includeClearanceRequired">
    /// Phase 136 Unit B. When false (default), notices flagged as high-confidence
    /// clearance-required are excluded entirely and the top-N is computed over the
    /// clearance-excluded set. When true, those notices are returned as an additive
    /// group APPENDED after the ranked top-N (flagged via
    /// <see cref="RecommendedOpportunityDto.ClearanceRequired"/>) so they never
    /// displace or count toward the top-N slots.
    /// </param>
    Task<List<RecommendedOpportunityDto>> GetRecommendedAsync(
        int orgId, int limit = 10, int? userId = null, bool includeClearanceRequired = false);

    /// <summary>
    /// Calculate OQS for a single opportunity against the org's profile.
    /// </summary>
    Task<RecommendedOpportunityDto?> CalculateOqScoreAsync(string noticeId, int orgId);

    /// <summary>
    /// Phase 136 Unit C. Returns ALL active "Sources Sought" and "Special Notice"
    /// notices matching the org's NAICS + certification profile (same set-aside cert
    /// rules as recommendations). These are NOT score-ranked and NOT capped at top-N;
    /// win-probability is irrelevant for market-research notices.
    /// </summary>
    Task<List<RecommendedOpportunityDto>> GetMarketResearchAsync(
        int orgId, int limit = 500, int? userId = null);
}
