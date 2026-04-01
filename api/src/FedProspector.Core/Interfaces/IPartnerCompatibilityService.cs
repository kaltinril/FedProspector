using FedProspector.Core.DTOs.Intelligence;

namespace FedProspector.Core.Interfaces;

public interface IPartnerCompatibilityService
{
    /// <summary>
    /// Score a specific partner for a specific opportunity.
    /// </summary>
    Task<PartnerScoreDto> ScorePartnerAsync(string partnerUei, string noticeId, int orgId);

    /// <summary>
    /// Find and score potential partners for an opportunity.
    /// </summary>
    Task<PartnerAnalysisDto> FindPartnersAsync(string noticeId, int orgId, int limit = 10);
}
