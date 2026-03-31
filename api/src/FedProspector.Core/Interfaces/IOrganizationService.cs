using FedProspector.Core.DTOs.Organizations;

namespace FedProspector.Core.Interfaces;

public interface IOrganizationService
{
    Task<OrganizationDto> GetOrganizationAsync(int orgId);
    Task<OrganizationDto> UpdateOrganizationAsync(int orgId, string name);
    Task<List<OrganizationMemberDto>> GetMembersAsync(int orgId);
    Task<InviteDto> CreateInviteAsync(int orgId, string email, string orgRole, int invitedBy);
    Task<List<InviteDto>> GetPendingInvitesAsync(int orgId);
    Task RevokeInviteAsync(int orgId, int inviteId);
    Task<List<OrganizationDto>> ListOrganizationsAsync();
    Task<OrganizationDto> CreateOrganizationAsync(string name, string slug);
    Task<OrganizationMemberDto> CreateOwnerAsync(int orgId, string email, string password, string displayName);
    Task<OrganizationMemberDto> CreateUserAsync(int orgId, string email, string password, string displayName, string orgRole, int createdBy);
}
