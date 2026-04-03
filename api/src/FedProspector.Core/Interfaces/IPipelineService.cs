using FedProspector.Core.DTOs.Pipeline;

namespace FedProspector.Core.Interfaces;

public interface IPipelineService
{
    Task<List<PipelineFunnelDto>> GetFunnelAsync(int organizationId);
    Task<List<PipelineCalendarEventDto>> GetCalendarEventsAsync(int organizationId, DateTime? startDate, DateTime? endDate);
    Task<List<StaleProspectDto>> GetStaleProspectsAsync(int organizationId);
    Task<List<RevenueForecastDto>> GetRevenueForecastAsync(int organizationId);
    Task<List<ProspectMilestoneDto>> GetMilestonesAsync(int prospectId, int organizationId);
    Task<ProspectMilestoneDto> CreateMilestoneAsync(int prospectId, int organizationId, CreateMilestoneRequest request);
    Task<ProspectMilestoneDto> UpdateMilestoneAsync(int milestoneId, int organizationId, UpdateMilestoneRequest request);
    Task<bool> DeleteMilestoneAsync(int milestoneId, int organizationId);
    Task<List<ProspectMilestoneDto>> GenerateReverseTimelineAsync(int prospectId, int organizationId, ReverseTimelineRequest request);
    Task<BulkStatusUpdateResult> BulkUpdateStatusAsync(int organizationId, int userId, BulkStatusUpdateRequest request);
    Task RecordStatusChangeAsync(int prospectId, string? oldStatus, string newStatus, int? userId);
}

public class BulkStatusUpdateResult
{
    public int Updated { get; set; }
    public int Skipped { get; set; }
    public List<string> Errors { get; set; } = new();
}
