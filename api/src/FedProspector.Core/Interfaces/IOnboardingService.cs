using FedProspector.Core.DTOs.Onboarding;

namespace FedProspector.Core.Interfaces;

public interface IOnboardingService
{
    Task<ProfileCompletenessDto> GetProfileCompletenessAsync(int organizationId);
    Task<UeiImportResultDto> ImportFromUeiAsync(int organizationId, string uei);
    Task<List<CertificationAlertDto>> GetCertificationAlertsAsync(int organizationId);
    Task<List<SizeStandardAlertDto>> GetSizeStandardAlertsAsync(int organizationId);
    Task<List<PastPerformanceRelevanceDto>> GetPastPerformanceRelevanceAsync(int organizationId, string? noticeId);
    Task<List<PortfolioGapDto>> GetPortfolioGapsAsync(int organizationId);
    Task<OrganizationPscDto> AddPscCodeAsync(int organizationId, string pscCode);
    Task<bool> RemovePscCodeAsync(int organizationId, int pscId);
    Task<List<OrganizationPscDto>> GetPscCodesAsync(int organizationId);
}
