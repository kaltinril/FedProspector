using FedProspector.Core.DTOs.Organizations;

namespace FedProspector.Core.Interfaces;

public interface IOrganizationEntityService
{
    Task<List<OrganizationEntityDto>> GetLinkedEntitiesAsync(int orgId);
    Task<OrganizationEntityDto> LinkEntityAsync(int orgId, int userId, LinkEntityRequest request);
    Task DeactivateLinkAsync(int orgId, int linkId);
    Task<RefreshSelfEntityResponse> RefreshFromSelfEntityAsync(int orgId);
    Task<List<string>> GetAggregateNaicsAsync(int orgId);
    Task<List<string>> GetLinkedUeisAsync(int orgId);
}
