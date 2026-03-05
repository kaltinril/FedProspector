using FedProspector.Core.DTOs.Organizations;

namespace FedProspector.Core.Interfaces;

public interface ICompanyProfileService
{
    Task<OrgProfileDto> GetProfileAsync(int orgId);
    Task<OrgProfileDto> UpdateProfileAsync(int orgId, UpdateOrgProfileRequest request);
    Task<List<OrgNaicsDto>> GetNaicsAsync(int orgId);
    Task<List<OrgNaicsDto>> SetNaicsAsync(int orgId, List<OrgNaicsDto> naicsCodes);
    Task<List<OrgCertificationDto>> GetCertificationsAsync(int orgId);
    Task<List<OrgCertificationDto>> SetCertificationsAsync(int orgId, List<OrgCertificationDto> certifications);
    Task<List<OrgPastPerformanceDto>> GetPastPerformancesAsync(int orgId);
    Task<OrgPastPerformanceDto> AddPastPerformanceAsync(int orgId, CreatePastPerformanceRequest request);
    Task<bool> DeletePastPerformanceAsync(int orgId, int id);
    Task<List<NaicsSearchDto>> SearchNaicsAsync(string query);
    Task<NaicsDetailDto?> GetNaicsDetailAsync(string code);
    Task<List<string>> GetCertificationTypesAsync();
}
