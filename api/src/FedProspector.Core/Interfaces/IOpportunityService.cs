using FedProspector.Core.DTOs;
using FedProspector.Core.DTOs.Opportunities;
using FedProspector.Core.Models;

namespace FedProspector.Core.Interfaces;

public interface IOpportunityService
{
    Task<PagedResponse<OpportunitySearchDto>> SearchAsync(OpportunitySearchRequest request, int organizationId, int? userId = null);
    Task<OpportunityDetailDto?> GetDetailAsync(string noticeId, int organizationId);
    Task<PagedResponse<TargetOpportunityDto>> GetTargetsAsync(TargetOpportunitySearchRequest request, int organizationId);
    Task<string> ExportCsvAsync(OpportunitySearchRequest request, int organizationId, int? userId = null);
    Task<FetchDescriptionResult> FetchDescriptionAsync(string noticeId, int? userId = null);
}
