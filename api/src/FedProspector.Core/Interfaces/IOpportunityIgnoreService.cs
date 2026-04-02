using FedProspector.Core.Models;

namespace FedProspector.Core.Interfaces;

public interface IOpportunityIgnoreService
{
    Task<OpportunityIgnore> IgnoreAsync(int userId, string noticeId, string? reason);
    Task UnignoreAsync(int userId, string noticeId);
    Task<HashSet<string>> GetIgnoredNoticeIdsAsync(int userId);
    Task<bool> IsIgnoredAsync(int userId, string noticeId);
}
