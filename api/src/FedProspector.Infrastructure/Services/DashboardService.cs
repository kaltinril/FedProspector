using FedProspector.Core.DTOs.Dashboard;
using FedProspector.Core.Interfaces;
using FedProspector.Infrastructure.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;

namespace FedProspector.Infrastructure.Services;

public class DashboardService : IDashboardService
{
    private readonly FedProspectorDbContext _context;
    private readonly ILogger<DashboardService> _logger;

    private static readonly string[] TerminalStatuses = ["WON", "LOST", "DECLINED", "NO_BID"];

    public DashboardService(FedProspectorDbContext context, ILogger<DashboardService> logger)
    {
        _context = context;
        _logger = logger;
    }

    public async Task<DashboardDto> GetDashboardAsync()
    {
        var statusCountsTask = GetProspectsByStatusAsync();
        var dueThisWeekTask = GetDueThisWeekAsync();
        var workloadTask = GetWorkloadByAssigneeAsync();
        var winLossTask = GetWinLossMetricsAsync();
        var savedSearchTask = GetRecentSavedSearchesAsync();
        var totalOpenTask = GetTotalOpenProspectsAsync();

        await Task.WhenAll(statusCountsTask, dueThisWeekTask, workloadTask,
            winLossTask, savedSearchTask, totalOpenTask);

        return new DashboardDto
        {
            ProspectsByStatus = await statusCountsTask,
            DueThisWeek = await dueThisWeekTask,
            WorkloadByAssignee = await workloadTask,
            WinLossMetrics = await winLossTask,
            RecentSavedSearches = await savedSearchTask,
            TotalOpenProspects = await totalOpenTask
        };
    }

    private async Task<List<StatusCountDto>> GetProspectsByStatusAsync()
    {
        return await _context.Prospects.AsNoTracking()
            .GroupBy(p => p.Status)
            .Select(g => new StatusCountDto { Status = g.Key, Count = g.Count() })
            .OrderBy(x => x.Status)
            .ToListAsync();
    }

    private async Task<List<DueOpportunityDto>> GetDueThisWeekAsync()
    {
        var now = DateTime.UtcNow;
        var weekOut = now.AddDays(7);

        return await (
            from p in _context.Prospects.AsNoTracking()
            join o in _context.Opportunities.AsNoTracking() on p.NoticeId equals o.NoticeId
            join u in _context.AppUsers.AsNoTracking() on p.AssignedTo equals u.UserId into uJoin
            from u in uJoin.DefaultIfEmpty()
            where !TerminalStatuses.Contains(p.Status)
               && o.ResponseDeadline != null
               && o.ResponseDeadline >= now
               && o.ResponseDeadline <= weekOut
            orderby o.ResponseDeadline
            select new DueOpportunityDto
            {
                ProspectId = p.ProspectId,
                Status = p.Status,
                Priority = p.Priority,
                Title = o.Title,
                ResponseDeadline = o.ResponseDeadline,
                SetAsideCode = o.SetAsideCode,
                AssignedTo = u != null ? u.DisplayName : null
            }
        ).ToListAsync();
    }

    private async Task<List<AssigneeWorkloadDto>> GetWorkloadByAssigneeAsync()
    {
        return await (
            from p in _context.Prospects.AsNoTracking()
            join u in _context.AppUsers.AsNoTracking() on p.AssignedTo equals u.UserId
            where !TerminalStatuses.Contains(p.Status)
            group p by new { u.Username, u.DisplayName } into g
            orderby g.Count() descending
            select new AssigneeWorkloadDto
            {
                Username = g.Key.Username,
                DisplayName = g.Key.DisplayName,
                Count = g.Count()
            }
        ).ToListAsync();
    }

    private async Task<List<OutcomeCountDto>> GetWinLossMetricsAsync()
    {
        return await _context.Prospects.AsNoTracking()
            .Where(p => p.Outcome != null)
            .GroupBy(p => p.Outcome!)
            .Select(g => new OutcomeCountDto { Outcome = g.Key, Count = g.Count() })
            .OrderBy(x => x.Outcome)
            .ToListAsync();
    }

    private async Task<List<SavedSearchSummaryDto>> GetRecentSavedSearchesAsync()
    {
        return await (
            from s in _context.SavedSearches.AsNoTracking()
            join u in _context.AppUsers.AsNoTracking() on s.UserId equals u.UserId
            where s.IsActive == "Y"
            orderby s.SearchName
            select new SavedSearchSummaryDto
            {
                SearchId = s.SearchId,
                SearchName = s.SearchName,
                Username = u.Username,
                LastRunAt = s.LastRunAt,
                LastNewResults = s.LastNewResults
            }
        ).ToListAsync();
    }

    private async Task<int> GetTotalOpenProspectsAsync()
    {
        return await _context.Prospects.AsNoTracking()
            .CountAsync(p => !TerminalStatuses.Contains(p.Status));
    }
}
