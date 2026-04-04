using FedProspector.Core.DTOs;
using FedProspector.Core.DTOs.Intelligence;

namespace FedProspector.Core.Interfaces;

public interface ITeamingService
{
    Task<PagedResponse<PartnerSearchResultDto>> SearchPartnersAsync(
        string? naicsCode, string? state, string? certification, string? agency, int page, int pageSize);

    Task<PartnerRiskDto?> GetPartnerRiskAsync(string uei);

    Task<PagedResponse<MentorProtegePairDto>> GetMentorProtegeCandidatesAsync(
        string? protegeUei, string? naicsCode, int page, int pageSize);

    Task<PagedResponse<PrimeSubRelationshipDto>> GetPrimeSubRelationshipsAsync(
        string uei, int page, int pageSize);

    Task<List<TeamingNetworkNodeDto>> GetTeamingNetworkAsync(string uei, int depth);

    Task<PartnerGapAnalysisDto> GetPartnerGapAnalysisAsync(int organizationId, string? naicsCode);
}
