using FedProspector.Core.DTOs;
using FedProspector.Core.DTOs.Entities;

namespace FedProspector.Core.Interfaces;

public interface IEntityService
{
    Task<PagedResponse<EntitySearchDto>> SearchAsync(EntitySearchRequest request);
    Task<EntityDetailDto?> GetDetailAsync(string uei);
    Task<CompetitorProfileDto?> GetCompetitorProfileAsync(string uei);
    Task<ExclusionCheckDto> CheckExclusionAsync(string uei);
}
