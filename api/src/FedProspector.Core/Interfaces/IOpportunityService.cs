using FedProspector.Core.DTOs;
using FedProspector.Core.DTOs.Opportunities;

namespace FedProspector.Core.Interfaces;

public interface IOpportunityService
{
    Task<PagedResponse<OpportunitySearchDto>> SearchAsync(OpportunitySearchRequest request);
    Task<OpportunityDetailDto?> GetDetailAsync(string noticeId);
    Task<PagedResponse<TargetOpportunityDto>> GetTargetsAsync(TargetOpportunitySearchRequest request);
}
