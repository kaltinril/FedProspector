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
        CreateMap<TargetOpportunityView, TargetOpportunityDto>();
        CreateMap<CompetitorAnalysisView, CompetitorProfileDto>()
            .ForMember(d => d.WinRate, opt => opt.Ignore())
            .ForMember(d => d.AverageContractSize, opt => opt.Ignore())
            .ForMember(d => d.RecentAwards, opt => opt.Ignore());

        // ----- Entity child table -> nested DTO mappings -----
        CreateMap<EntityAddress, EntityAddressDto>();
        CreateMap<EntityNaics, EntityNaicsDto>();
        CreateMap<EntityPsc, EntityPscDto>();
        CreateMap<EntityBusinessType, EntityBusinessTypeDto>();
        CreateMap<EntitySbaCertification, EntitySbaCertificationDto>();
        CreateMap<EntityPoc, EntityPocDto>();

        // ----- Simple model -> DTO mappings -----
        CreateMap<SamExclusion, ExclusionDto>();
        CreateMap<SavedSearch, SavedSearchDto>()
            .ForMember(d => d.FilterCriteria, opt => opt.MapFrom(s => s.FilterCriteria));
    }
}
