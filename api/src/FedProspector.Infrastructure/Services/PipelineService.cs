using FedProspector.Core.DTOs.Pipeline;
using FedProspector.Core.Interfaces;
using FedProspector.Core.Models;
using FedProspector.Infrastructure.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;

namespace FedProspector.Infrastructure.Services;

public class PipelineService : IPipelineService
{
    private readonly FedProspectorDbContext _context;
    private readonly ILogger<PipelineService> _logger;

    // Built-in reverse-timeline templates: milestone name -> days before deadline
    private static readonly Dictionary<string, List<(string Name, int DaysBefore)>> Templates = new()
    {
        ["standard_rfp"] = new()
        {
            ("Final Submission", 0),
            ("Final Review", 2),
            ("Management Review", 5),
            ("Draft Response Complete", 10),
            ("Outline & Compliance Matrix", 15),
            ("Kickoff / Requirements Analysis", 20)
        },
        ["quick_quote"] = new()
        {
            ("Final Submission", 0),
            ("Final Review", 1),
            ("Draft Response", 3),
            ("Requirements Review", 5)
        },
        ["large_proposal"] = new()
        {
            ("Final Submission", 0),
            ("Final Review", 3),
            ("Red Team Review", 7),
            ("Pink Team Review", 14),
            ("Draft Response Complete", 21),
            ("Outline & Compliance Matrix", 28),
            ("Kickoff / Requirements Analysis", 35)
        }
    };

    public PipelineService(FedProspectorDbContext context, ILogger<PipelineService> logger)
    {
        _context = context;
        _logger = logger;
    }

    public async Task<List<PipelineFunnelDto>> GetFunnelAsync(int organizationId)
    {
        var rows = await _context.PipelineFunnels.AsNoTracking()
            .Where(f => f.OrganizationId == organizationId)
            .ToListAsync();

        return rows.Select(r => new PipelineFunnelDto
        {
            Status = r.Status,
            ProspectCount = r.ProspectCount,
            TotalEstimatedValue = r.TotalEstimatedValue,
            AvgHoursInPriorStatus = r.AvgHoursInPriorStatus,
            WinRatePct = r.WinRatePct,
            WonCount = r.WonCount,
            LostCount = r.LostCount
        }).ToList();
    }

    public async Task<List<PipelineCalendarEventDto>> GetCalendarEventsAsync(
        int organizationId, DateTime? startDate, DateTime? endDate)
    {
        var query = _context.PipelineCalendarEvents.AsNoTracking()
            .Where(c => c.OrganizationId == organizationId);

        if (startDate.HasValue)
            query = query.Where(c => c.ResponseDeadline >= startDate.Value);

        if (endDate.HasValue)
            query = query.Where(c => c.ResponseDeadline <= endDate.Value);

        var rows = await query.OrderBy(c => c.ResponseDeadline).ToListAsync();

        return rows.Select(r => new PipelineCalendarEventDto
        {
            ProspectId = r.ProspectId,
            NoticeId = r.NoticeId,
            OpportunityTitle = r.OpportunityTitle,
            ResponseDeadline = r.ResponseDeadline,
            SolicitationNumber = r.SolicitationNumber,
            Status = r.Status,
            Priority = r.Priority,
            AssignedTo = r.AssignedTo,
            AssignedToName = r.AssignedToName,
            EstimatedValue = r.EstimatedValue,
            WinProbability = r.WinProbability
        }).ToList();
    }

    public async Task<List<StaleProspectDto>> GetStaleProspectsAsync(int organizationId)
    {
        var rows = await _context.StaleProspects.AsNoTracking()
            .Where(s => s.OrganizationId == organizationId)
            .OrderByDescending(s => s.DaysSinceUpdate)
            .ToListAsync();

        return rows.Select(r => new StaleProspectDto
        {
            ProspectId = r.ProspectId,
            NoticeId = r.NoticeId,
            OpportunityTitle = r.OpportunityTitle,
            Status = r.Status,
            Priority = r.Priority,
            DaysSinceUpdate = r.DaysSinceUpdate,
            AssignedTo = r.AssignedTo,
            AssignedToName = r.AssignedToName,
            EstimatedValue = r.EstimatedValue,
            LastUpdatedAt = r.LastUpdatedAt
        }).ToList();
    }

    public async Task<List<RevenueForecastDto>> GetRevenueForecastAsync(int organizationId)
    {
        var rows = await _context.PipelineRevenueForecasts.AsNoTracking()
            .Where(f => f.OrganizationId == organizationId)
            .OrderBy(f => f.ForecastMonth)
            .ToListAsync();

        return rows.Select(r => new RevenueForecastDto
        {
            ForecastMonth = r.ForecastMonth,
            ProspectCount = r.ProspectCount,
            TotalUnweightedValue = r.TotalUnweightedValue,
            TotalWeightedValue = r.TotalWeightedValue,
            AvgWinProbability = r.AvgWinProbability
        }).ToList();
    }

    public async Task<List<ProspectMilestoneDto>> GetMilestonesAsync(int prospectId, int organizationId)
    {
        // Verify prospect belongs to org
        var prospect = await _context.Prospects.AsNoTracking()
            .FirstOrDefaultAsync(p => p.ProspectId == prospectId && p.OrganizationId == organizationId);
        if (prospect == null)
            return new List<ProspectMilestoneDto>();

        var milestones = await _context.ProspectMilestones.AsNoTracking()
            .Where(m => m.ProspectId == prospectId)
            .OrderBy(m => m.SortOrder)
            .ThenBy(m => m.TargetDate)
            .ToListAsync();

        return milestones.Select(MapMilestoneDto).ToList();
    }

    public async Task<ProspectMilestoneDto> CreateMilestoneAsync(
        int prospectId, int organizationId, CreateMilestoneRequest request)
    {
        var prospect = await _context.Prospects.AsNoTracking()
            .FirstOrDefaultAsync(p => p.ProspectId == prospectId && p.OrganizationId == organizationId)
            ?? throw new KeyNotFoundException($"Prospect {prospectId} not found in organization");

        var milestone = new ProspectMilestone
        {
            ProspectId = prospectId,
            MilestoneName = request.MilestoneName,
            TargetDate = request.TargetDate,
            IsCompleted = false,
            SortOrder = request.SortOrder,
            Notes = request.Notes,
            CreatedAt = DateTime.UtcNow,
            UpdatedAt = DateTime.UtcNow
        };

        _context.ProspectMilestones.Add(milestone);
        await _context.SaveChangesAsync();

        return MapMilestoneDto(milestone);
    }

    public async Task<ProspectMilestoneDto> UpdateMilestoneAsync(
        int milestoneId, int organizationId, UpdateMilestoneRequest request)
    {
        var milestone = await _context.ProspectMilestones
            .Include(m => m.Prospect)
            .FirstOrDefaultAsync(m => m.ProspectMilestoneId == milestoneId)
            ?? throw new KeyNotFoundException($"Milestone {milestoneId} not found");

        if (milestone.Prospect?.OrganizationId != organizationId)
            throw new KeyNotFoundException($"Milestone {milestoneId} not found in organization");

        if (request.MilestoneName != null)
            milestone.MilestoneName = request.MilestoneName;
        if (request.TargetDate.HasValue)
            milestone.TargetDate = request.TargetDate.Value;
        if (request.CompletedDate.HasValue)
            milestone.CompletedDate = request.CompletedDate.Value;
        if (request.IsCompleted.HasValue)
        {
            milestone.IsCompleted = request.IsCompleted.Value;
            if (milestone.IsCompleted && !milestone.CompletedDate.HasValue)
                milestone.CompletedDate = DateOnly.FromDateTime(DateTime.UtcNow);
        }
        if (request.SortOrder.HasValue)
            milestone.SortOrder = request.SortOrder.Value;
        milestone.Notes = request.Notes;

        milestone.UpdatedAt = DateTime.UtcNow;
        await _context.SaveChangesAsync();

        return MapMilestoneDto(milestone);
    }

    public async Task<bool> DeleteMilestoneAsync(int milestoneId, int organizationId)
    {
        var milestone = await _context.ProspectMilestones
            .Include(m => m.Prospect)
            .FirstOrDefaultAsync(m => m.ProspectMilestoneId == milestoneId);

        if (milestone == null || milestone.Prospect?.OrganizationId != organizationId)
            return false;

        _context.ProspectMilestones.Remove(milestone);
        await _context.SaveChangesAsync();
        return true;
    }

    public async Task<List<ProspectMilestoneDto>> GenerateReverseTimelineAsync(
        int prospectId, int organizationId, ReverseTimelineRequest request)
    {
        var prospect = await _context.Prospects.AsNoTracking()
            .FirstOrDefaultAsync(p => p.ProspectId == prospectId && p.OrganizationId == organizationId)
            ?? throw new KeyNotFoundException($"Prospect {prospectId} not found in organization");

        // Prevent duplicate milestone generation
        var existingCount = await _context.ProspectMilestones.CountAsync(m => m.ProspectId == prospectId);
        if (existingCount > 0)
            throw new InvalidOperationException($"Prospect already has {existingCount} milestones. Delete existing milestones first or use the update endpoint.");

        // Resolve milestone definitions
        List<(string Name, int DaysBefore)> definitions;

        if (request.CustomMilestones != null && request.CustomMilestones.Count > 0)
        {
            definitions = request.CustomMilestones
                .Select(m => (m.MilestoneName, m.DaysBeforeDeadline))
                .ToList();
        }
        else
        {
            var templateName = request.TemplateName ?? "standard_rfp";
            if (!Templates.TryGetValue(templateName, out var template))
                throw new InvalidOperationException(
                    $"Unknown template '{templateName}'. Available: {string.Join(", ", Templates.Keys)}");
            definitions = template;
        }

        // Sort by days before (descending = earliest milestone first)
        definitions = definitions.OrderByDescending(d => d.DaysBefore).ToList();

        var milestones = new List<ProspectMilestone>();
        for (int i = 0; i < definitions.Count; i++)
        {
            var (name, daysBefore) = definitions[i];
            milestones.Add(new ProspectMilestone
            {
                ProspectId = prospectId,
                MilestoneName = name,
                TargetDate = request.ResponseDeadline.AddDays(-daysBefore),
                IsCompleted = false,
                SortOrder = i,
                CreatedAt = DateTime.UtcNow,
                UpdatedAt = DateTime.UtcNow
            });
        }

        _context.ProspectMilestones.AddRange(milestones);
        await _context.SaveChangesAsync();

        return milestones.Select(MapMilestoneDto).ToList();
    }

    // Valid prospect statuses (must match ProspectService.StatusFlow keys + terminal values)
    private static readonly HashSet<string> ValidStatuses = new()
    {
        "NEW", "REVIEWING", "PURSUING", "BID_SUBMITTED", "WON", "LOST", "DECLINED", "NO_BID"
    };

    public async Task<BulkStatusUpdateResult> BulkUpdateStatusAsync(
        int organizationId, int userId, BulkStatusUpdateRequest request)
    {
        var result = new BulkStatusUpdateResult();

        // Validate new status is a known value
        if (!ValidStatuses.Contains(request.NewStatus))
        {
            result.Errors.Add($"Invalid status '{request.NewStatus}'. Valid values: {string.Join(", ", ValidStatuses.Order())}");
            result.Skipped = request.ProspectIds.Count;
            return result;
        }

        // Deduplicate prospect IDs
        var prospectIds = request.ProspectIds.Distinct().ToList();

        // Load all requested prospects that belong to the org
        var prospects = await _context.Prospects
            .Where(p => prospectIds.Contains(p.ProspectId) && p.OrganizationId == organizationId)
            .ToListAsync();

        // Check for IDs not found in the org
        var foundIds = prospects.Select(p => p.ProspectId).ToHashSet();
        foreach (var id in prospectIds)
        {
            if (!foundIds.Contains(id))
            {
                result.Errors.Add($"Prospect {id} not found in organization");
                result.Skipped++;
            }
        }

        var terminalStatuses = new HashSet<string> { "WON", "LOST", "DECLINED", "NO_BID" };

        foreach (var prospect in prospects)
        {
            if (terminalStatuses.Contains(prospect.Status))
            {
                result.Errors.Add($"Prospect {prospect.ProspectId} is in terminal status '{prospect.Status}'");
                result.Skipped++;
                continue;
            }

            var oldStatus = prospect.Status;
            prospect.Status = request.NewStatus;
            prospect.UpdatedAt = DateTime.UtcNow;

            if (terminalStatuses.Contains(request.NewStatus))
            {
                prospect.Outcome = request.NewStatus;
                prospect.OutcomeDate = DateOnly.FromDateTime(DateTime.UtcNow);
                if (!string.IsNullOrEmpty(request.Notes))
                    prospect.OutcomeNotes = request.Notes;
            }

            if (request.NewStatus == "BID_SUBMITTED")
                prospect.BidSubmittedDate = DateOnly.FromDateTime(DateTime.UtcNow);

            // Record status history
            await RecordStatusChangeAsync(prospect.ProspectId, oldStatus, request.NewStatus, userId);

            result.Updated++;
        }

        await _context.SaveChangesAsync();
        return result;
    }

    public async Task RecordStatusChangeAsync(int prospectId, string? oldStatus, string newStatus, int? userId)
    {
        // Calculate time in old status if we have history
        int? timeInOldHours = null;
        if (oldStatus != null)
        {
            var lastEntry = await _context.ProspectStatusHistories.AsNoTracking()
                .Where(h => h.ProspectId == prospectId)
                .OrderByDescending(h => h.ChangedAt)
                .FirstOrDefaultAsync();

            if (lastEntry != null)
            {
                timeInOldHours = (int)(DateTime.UtcNow - lastEntry.ChangedAt).TotalHours;
            }
        }

        var history = new ProspectStatusHistory
        {
            ProspectId = prospectId,
            OldStatus = oldStatus,
            NewStatus = newStatus,
            ChangedBy = userId,
            ChangedAt = DateTime.UtcNow,
            TimeInOldStatusHours = timeInOldHours
        };

        _context.ProspectStatusHistories.Add(history);
        // SaveChanges is called by the caller (or in bulk at the end)
    }

    private static ProspectMilestoneDto MapMilestoneDto(ProspectMilestone m)
    {
        return new ProspectMilestoneDto
        {
            ProspectMilestoneId = m.ProspectMilestoneId,
            ProspectId = m.ProspectId,
            MilestoneName = m.MilestoneName,
            TargetDate = m.TargetDate,
            CompletedDate = m.CompletedDate,
            IsCompleted = m.IsCompleted,
            SortOrder = m.SortOrder,
            Notes = m.Notes,
            CreatedAt = m.CreatedAt,
            UpdatedAt = m.UpdatedAt
        };
    }
}
