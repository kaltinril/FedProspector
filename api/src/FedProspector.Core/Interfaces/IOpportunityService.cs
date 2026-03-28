using FedProspector.Core.DTOs;
using FedProspector.Core.DTOs.Opportunities;

namespace FedProspector.Core.Interfaces;

public interface IOpportunityService
{
    Task<PagedResponse<OpportunitySearchDto>> SearchAsync(OpportunitySearchRequest request, int organizationId);
    Task<OpportunityDetailDto?> GetDetailAsync(string noticeId, int organizationId);
    Task<PagedResponse<TargetOpportunityDto>> GetTargetsAsync(TargetOpportunitySearchRequest request, int organizationId);
    Task<string> ExportCsvAsync(OpportunitySearchRequest request, int organizationId);
    Task<(string? descriptionText, string? error, bool notFound)> FetchDescriptionAsync(string noticeId);
}
