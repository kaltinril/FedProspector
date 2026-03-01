using AutoMapper;

namespace FedProspector.Core.Mapping;

public class MappingProfile : Profile
{
    public MappingProfile()
    {
        // Opportunity -> OpportunityDto mapping will be added in Phase 11
        // This profile is registered via assembly scanning
    }
}
