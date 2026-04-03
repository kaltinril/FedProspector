using FedProspector.Core.DTOs;
using FedProspector.Core.DTOs.Intelligence;

namespace FedProspector.Core.Interfaces;

public interface ICompetitiveIntelService
{
    Task<PagedResponse<RecompeteCandidateDto>> GetRecompeteCandidatesAsync(
        string? naicsCode, string? agencyCode, string? setAsideCode, int page, int pageSize);

    Task<List<AgencyRecompetePatternDto>> GetAgencyRecompetePatternsAsync(
        string? agencyCode, string? officeCode);

    Task<CompetitorDossierDto?> GetCompetitorDossierAsync(string uei);

    Task<List<AgencyBuyingPatternDto>> GetAgencyBuyingPatternsAsync(string agencyCode, int? year);

    Task<ContractingOfficeProfileDto?> GetContractingOfficeProfileAsync(string officeCode);

    Task<PagedResponse<ContractingOfficeProfileDto>> SearchContractingOfficesAsync(
        string? agencyCode, string? search, int page, int pageSize);
}
