using FedProspector.Core.DTOs;
using FedProspector.Core.DTOs.Subawards;

namespace FedProspector.Core.Interfaces;

public interface ISubawardService
{
    Task<PagedResponse<TeamingPartnerDto>> GetTeamingPartnersAsync(TeamingPartnerSearchRequest request);
    Task<List<SubawardDetailDto>> GetSubawardsByPrimeContractAsync(string primePiid);
}
