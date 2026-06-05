using FedProspector.Core.DTOs.Organizations;

namespace FedProspector.Core.Interfaces;

public interface IOrganizationEntityService
{
    Task<List<OrganizationEntityDto>> GetLinkedEntitiesAsync(int orgId);
    Task<OrganizationEntityDto> LinkEntityAsync(int orgId, int userId, LinkEntityRequest request);

    /// <summary>
    /// Phase 136 Unit F: update an existing linked entity's editable data (affiliate
    /// revenue/employees, MPA flag/date, notes, partner UEI) at any time after the link
    /// is created. Null request fields are left unchanged.
    /// </summary>
    Task<OrganizationEntityDto> UpdateLinkAsync(int orgId, int linkId, UpdateEntityLinkRequest request);

    Task DeactivateLinkAsync(int orgId, int linkId);
    Task<RefreshSelfEntityResponse> RefreshFromSelfEntityAsync(int orgId);
    Task<List<string>> GetAggregateNaicsAsync(int orgId);
    Task<List<string>> GetLinkedUeisAsync(int orgId);
    Task<int> SyncEntityCertsAsync(int orgId);
    Task<int> ResyncAllOrgsAsync();
}
