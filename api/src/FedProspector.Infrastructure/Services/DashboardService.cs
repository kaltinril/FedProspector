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

    public async Task<DashboardDto> GetDashboardAsync(int organizationId)
    {
        // EF Core DbContext is not thread-safe — queries must run sequentially
        var statusCounts = await GetProspectsByStatusAsync(organizationId);
        var dueThisWeek = await GetDueThisWeekAsync(organizationId);
        var workload = await GetWorkloadByAssigneeAsync(organizationId);
        var winLoss = await GetWinLossMetricsAsync(organizationId);
        var savedSearches = await GetRecentSavedSearchesAsync(organizationId);
        var totalOpen = await GetTotalOpenProspectsAsync(organizationId);
        var pipelineValue = await GetPipelineValueAsync(organizationId);

        return new DashboardDto
        {
            ProspectsByStatus = statusCounts,
            DueThisWeek = dueThisWeek,
            WorkloadByAssignee = workload,
            WinLossMetrics = winLoss,
            RecentSavedSearches = savedSearches,
            TotalOpenProspects = totalOpen,
            PipelineValue = pipelineValue
        };
    }

    private async Task<List<StatusCountDto>> GetProspectsByStatusAsync(int organizationId)
    {
        return await _context.Prospects.AsNoTracking()
            .Where(p => p.OrganizationId == organizationId)
            .GroupBy(p => p.Status)
            .Select(g => new StatusCountDto { Status = g.Key, Count = g.Count() })
            .OrderBy(x => x.Status)
            .ToListAsync();
    }

    private async Task<List<DueOpportunityDto>> GetDueThisWeekAsync(int organizationId)
    {
        var now = DateTime.UtcNow;
        var weekOut = now.AddDays(7);

        return await (
            from p in _context.Prospects.AsNoTracking()
            join o in _context.Opportunities.AsNoTracking() on p.NoticeId equals o.NoticeId
            join u in _context.AppUsers.AsNoTracking() on p.AssignedTo equals u.UserId into uJoin
            from u in uJoin.DefaultIfEmpty()
            where p.OrganizationId == organizationId
               && !TerminalStatuses.Contains(p.Status)
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

    private async Task<List<AssigneeWorkloadDto>> GetWorkloadByAssigneeAsync(int organizationId)
    {
        return await (
            from p in _context.Prospects.AsNoTracking()
            join u in _context.AppUsers.AsNoTracking() on p.AssignedTo equals u.UserId
            where p.OrganizationId == organizationId
               && !TerminalStatuses.Contains(p.Status)
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

    private async Task<List<OutcomeCountDto>> GetWinLossMetricsAsync(int organizationId)
    {
        return await _context.Prospects.AsNoTracking()
            .Where(p => p.OrganizationId == organizationId && p.Outcome != null)
            .GroupBy(p => p.Outcome!)
            .Select(g => new OutcomeCountDto { Outcome = g.Key, Count = g.Count() })
            .OrderBy(x => x.Outcome)
            .ToListAsync();
    }

    private async Task<List<SavedSearchSummaryDto>> GetRecentSavedSearchesAsync(int organizationId)
    {
        return await (
            from s in _context.SavedSearches.AsNoTracking()
            join u in _context.AppUsers.AsNoTracking() on s.UserId equals u.UserId
            where s.OrganizationId == organizationId && s.IsActive == "Y"
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

    private async Task<int> GetTotalOpenProspectsAsync(int organizationId)
    {
        return await _context.Prospects.AsNoTracking()
            .CountAsync(p => p.OrganizationId == organizationId && !TerminalStatuses.Contains(p.Status));
    }

    private async Task<decimal> GetPipelineValueAsync(int organizationId)
    {
        return await _context.Prospects.AsNoTracking()
            .Where(p => p.OrganizationId == organizationId
                     && !TerminalStatuses.Contains(p.Status)
                     && p.EstimatedValue.HasValue)
            .SumAsync(p => p.EstimatedValue!.Value);
    }
}
