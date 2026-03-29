using FedProspector.Core.DTOs;
using FedProspector.Core.DTOs.FederalHierarchy;
using FedProspector.Core.DTOs.Opportunities;
using FedProspector.Core.DTOs.Awards;

namespace FedProspector.Core.Interfaces;

public interface IFederalHierarchyService
{
    Task<PagedResponse<FederalOrgListItemDto>> SearchAsync(FederalOrgSearchRequestDto request);
    Task<FederalOrgDetailDto?> GetDetailAsync(int fhOrgId);
    Task<List<FederalOrgListItemDto>> GetChildrenAsync(int fhOrgId, string? status = null, string? keyword = null);
    Task<List<FederalOrgTreeNodeDto>> GetTreeAsync(string? keyword = null);
    Task<PagedResponse<OpportunitySearchDto>> GetOpportunitiesAsync(int fhOrgId, PagedRequest request, string? active = null, string? type = null, string? setAsideCode = null);
    Task<PagedResponse<AwardSearchDto>> GetAwardsAsync(int fhOrgId, PagedRequest request);
    Task<FederalOrgStatsDto> GetStatsAsync(int fhOrgId);
    Task<HierarchyRefreshStatusDto> GetRefreshStatusAsync();
}
