using AutoMapper;
using FedProspector.Core.Models;
using FedProspector.Core.Models.Views;
using FedProspector.Core.DTOs.Opportunities;
using FedProspector.Core.DTOs.Awards;
using FedProspector.Core.DTOs.Entities;
using FedProspector.Core.DTOs.SavedSearches;

namespace FedProspector.Core.Mapping;

public class MappingProfile : Profile
{
    public MappingProfile()
    {
        // ----- View -> DTO mappings -----
        // Phase 132: the target view has no normalized solicitation column; the
        // service derives SolicitationNumberNormalized from the original after mapping.
        CreateMap<TargetOpportunityView, TargetOpportunityDto>()
            .ForMember(d => d.SolicitationNumberNormalized, opt => opt.Ignore());
        CreateMap<CompetitorAnalysisView, CompetitorProfileDto>()
            .ForMember(d => d.WinRate, opt => opt.Ignore())
            .ForMember(d => d.AverageContractSize, opt => opt.Ignore())
            .ForMember(d => d.RecentAwards, opt => opt.Ignore());

        // ----- Entity child table -> nested DTO mappings -----
        CreateMap<EntityAddress, EntityAddressDto>()
            .ForMember(d => d.CountryName, opt => opt.Ignore());
        CreateMap<EntityNaics, EntityNaicsDto>()
            .ForMember(d => d.NaicsDescription, opt => opt.Ignore());
        CreateMap<EntityPsc, EntityPscDto>()
            .ForMember(d => d.PscDescription, opt => opt.Ignore());
        CreateMap<EntityBusinessType, EntityBusinessTypeDto>()
            .ForMember(d => d.BusinessTypeDescription, opt => opt.Ignore());
        CreateMap<EntitySbaCertification, EntitySbaCertificationDto>();
        CreateMap<EntityPoc, EntityPocDto>();

        // ----- Simple model -> DTO mappings -----
        CreateMap<SamExclusion, ExclusionDto>();
        CreateMap<SavedSearch, SavedSearchDto>()
            .ForMember(d => d.FilterCriteria, opt => opt.MapFrom(s => s.FilterCriteria));
    }
}
