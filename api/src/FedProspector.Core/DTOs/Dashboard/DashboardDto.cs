namespace FedProspector.Core.DTOs.Dashboard;

public class DashboardDto
{
    public List<StatusCountDto> ProspectsByStatus { get; set; } = [];
    public List<DueOpportunityDto> DueThisWeek { get; set; } = [];
    public List<AssigneeWorkloadDto> WorkloadByAssignee { get; set; } = [];
    public List<OutcomeCountDto> WinLossMetrics { get; set; } = [];
    public List<SavedSearchSummaryDto> RecentSavedSearches { get; set; } = [];
    public int TotalOpenProspects { get; set; }
}
