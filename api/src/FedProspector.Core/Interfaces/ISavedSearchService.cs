using FedProspector.Core.DTOs.SavedSearches;

namespace FedProspector.Core.Interfaces;

public interface ISavedSearchService
{
    Task<IEnumerable<SavedSearchDto>> ListAsync(int userId);
    Task<SavedSearchDto?> GetByIdAsync(int searchId, int userId);
    Task<SavedSearchDto> CreateAsync(int userId, int organizationId, CreateSavedSearchRequest request);
    Task<SavedSearchRunResultDto?> RunAsync(int userId, int searchId);
    Task<bool> DeleteAsync(int userId, int searchId);
    Task<SavedSearchDto?> UpdateAsync(int userId, int searchId, UpdateSavedSearchRequest request);
}
