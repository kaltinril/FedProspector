using FedProspector.Core.DTOs.Intelligence;

namespace FedProspector.Core.Interfaces;

public interface IRecommendedOpportunityService
{
    Task<List<RecommendedOpportunityDto>> GetRecommendedAsync(int orgId, int limit = 10);
}
