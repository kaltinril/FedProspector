using FedProspector.Core.DTOs.Intelligence;

namespace FedProspector.Core.Interfaces;

public interface ICompetitorStrengthService
{
    /// <summary>
    /// Get CSI scores for top competitors in a NAICS code (general market view).
    /// </summary>
    Task<CompetitorAnalysisDto> GetMarketCompetitorsAsync(string naicsCode, int years = 3, int limit = 10);

    /// <summary>
    /// Get CSI scores for likely competitors on a specific opportunity (context-specific).
    /// </summary>
    Task<CompetitorAnalysisDto> GetOpportunityCompetitorsAsync(string noticeId, int limit = 10);

    /// <summary>
    /// Get detailed CSI for a single competitor.
    /// </summary>
    Task<CompetitorScoreDto?> GetCompetitorDetailAsync(string competitorUei, string? naicsCode = null, string? agencyCode = null);
}
