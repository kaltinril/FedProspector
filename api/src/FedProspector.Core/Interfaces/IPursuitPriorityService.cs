using FedProspector.Core.DTOs.Intelligence;

namespace FedProspector.Core.Interfaces;

public interface IPursuitPriorityService
{
    Task<PursuitPriorityDto> CalculateAsync(string noticeId, int orgId);
    Task<List<PursuitPriorityDto>> CalculateBatchAsync(List<string> noticeIds, int orgId);
}
