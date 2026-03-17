using FedProspector.Core.DTOs;
using FedProspector.Core.DTOs.Prospects;
using FedProspector.Core.Interfaces;
using FedProspector.Core.Models;
using FedProspector.Infrastructure.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;

namespace FedProspector.Infrastructure.Services;

public class ProspectService : IProspectService
{
    private readonly FedProspectorDbContext _context;
    private readonly IGoNoGoScoringService _scoringService;
    private readonly IActivityLogService _activityLog;
    private readonly INotificationService _notificationService;
    private readonly ILogger<ProspectService> _logger;

    private static readonly Dictionary<string, string[]> StatusFlow = new()
    {
        ["NEW"] = new[] { "REVIEWING", "DECLINED" },
        ["REVIEWING"] = new[] { "PURSUING", "DECLINED", "NO_BID" },
        ["PURSUING"] = new[] { "BID_SUBMITTED", "DECLINED" },
        ["BID_SUBMITTED"] = new[] { "WON", "LOST" }
    };

    private static readonly HashSet<string> TerminalStatuses = new()
    {
        "WON", "LOST", "DECLINED", "NO_BID"
    };

    public ProspectService(
        FedProspectorDbContext context,
        IGoNoGoScoringService scoringService,
        IActivityLogService activityLog,
        INotificationService notificationService,
        ILogger<ProspectService> logger)
    {
        _context = context;
        _scoringService = scoringService;
        _activityLog = activityLog;
        _notificationService = notificationService;
        _logger = logger;
    }

    public async Task<ProspectDetailDto> CreateAsync(int userId, int organizationId, CreateProspectRequest request)
    {
        // Validate opportunity exists
        var oppExists = await _context.Opportunities.AnyAsync(o => o.NoticeId == request.NoticeId);
        if (!oppExists)
            throw new InvalidOperationException($"Opportunity with notice ID '{request.NoticeId}' not found");

        // Check for existing prospect within this organization
        var prospectExists = await _context.Prospects.AnyAsync(p => p.NoticeId == request.NoticeId && p.OrganizationId == organizationId);
        if (prospectExists)
            throw new InvalidOperationException($"A prospect already exists for opportunity '{request.NoticeId}'");

        // Validate assignee if provided
        if (request.AssignedTo.HasValue)
        {
            var assignee = await _context.AppUsers.AsNoTracking()
                .FirstOrDefaultAsync(u => u.UserId == request.AssignedTo.Value && u.OrganizationId == organizationId);
            if (assignee == null || assignee.IsActive != "Y")
                throw new InvalidOperationException($"User {request.AssignedTo.Value} not found or not active");
        }

        // Fix 6: Validate capture manager belongs to the same organization
        if (request.CaptureManagerId.HasValue)
        {
            var captureManager = await _context.AppUsers.AsNoTracking()
                .FirstOrDefaultAsync(u => u.UserId == request.CaptureManagerId.Value
                                          && u.OrganizationId == organizationId);
            if (captureManager == null)
                throw new KeyNotFoundException("CaptureManagerId not found in organization.");
        }

        var priority = request.Priority ?? "MEDIUM";

        var prospect = new Prospect
        {
            OrganizationId = organizationId,
            NoticeId = request.NoticeId,
            AssignedTo = request.AssignedTo,
            CaptureManagerId = request.CaptureManagerId,
            Status = "NEW",
            Priority = priority,
            CreatedAt = DateTime.UtcNow,
            UpdatedAt = DateTime.UtcNow
        };

        _context.Prospects.Add(prospect);
        await _context.SaveChangesAsync();

        // Auto-create STATUS_CHANGE note
        var noteText = $"Prospect created with status NEW, priority {priority}.";
        if (!string.IsNullOrWhiteSpace(request.Notes))
            noteText += $" {request.Notes}";

        var note = new ProspectNote
        {
            ProspectId = prospect.ProspectId,
            UserId = userId,
            NoteType = "STATUS_CHANGE",
            NoteText = noteText,
            CreatedAt = DateTime.UtcNow
        };

        _context.ProspectNotes.Add(note);
        await _context.SaveChangesAsync();

        // Auto-calculate Go/No-Go score
        try
        {
            await _scoringService.CalculateScoreAsync(prospect.ProspectId, organizationId);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to calculate Go/No-Go score for prospect {ProspectId}", prospect.ProspectId);
        }

        // Log activity
        await _activityLog.LogAsync(organizationId, userId, "CREATE_PROSPECT", "PROSPECT", prospect.ProspectId.ToString());

        // Notify assigned user of new prospect
        if (prospect.AssignedTo.HasValue)
        {
            await _notificationService.CreateNotificationAsync(
                prospect.AssignedTo.Value,
                "PROSPECT_ASSIGNED",
                "New prospect assigned to you",
                $"A new prospect for opportunity {request.NoticeId} has been assigned to you",
                "PROSPECT",
                prospect.ProspectId.ToString());
        }

        return (await GetDetailAsync(organizationId, prospect.ProspectId))!;
    }

    public async Task<PagedResponse<ProspectListDto>> SearchAsync(int organizationId, ProspectSearchRequest request)
    {
        var query = _context.Prospects.AsNoTracking()
            .Where(p => p.OrganizationId == organizationId);

        // Apply filters
        if (!string.IsNullOrWhiteSpace(request.Status))
            query = query.Where(p => p.Status == request.Status);

        if (request.AssignedTo.HasValue)
            query = query.Where(p => p.AssignedTo == request.AssignedTo.Value);

        if (request.CaptureManagerId.HasValue)
            query = query.Where(p => p.CaptureManagerId == request.CaptureManagerId.Value);

        if (!string.IsNullOrWhiteSpace(request.Priority))
            query = query.Where(p => p.Priority == request.Priority);

        if (!string.IsNullOrWhiteSpace(request.Source))
            query = query.Where(p => p.Source == request.Source);

        if (request.OpenOnly)
            query = query.Where(p => p.Status != "WON" && p.Status != "LOST" && p.Status != "DECLINED" && p.Status != "NO_BID");

        // NAICS filter: correlated subquery to avoid duplicate rows from joins
        if (!string.IsNullOrWhiteSpace(request.Naics))
        {
            var naicsFilter = request.Naics;
            query = query.Where(p => _context.Opportunities.Any(o =>
                o.NoticeId == p.NoticeId && o.NaicsCode != null && o.NaicsCode.StartsWith(naicsFilter)));
        }

        // SetAside filter: correlated subquery to avoid duplicate rows from joins
        if (!string.IsNullOrWhiteSpace(request.SetAside))
        {
            var setAsideFilter = request.SetAside;
            query = query.Where(p => _context.Opportunities.Any(o =>
                o.NoticeId == p.NoticeId && o.SetAsideCode == setAsideFilter));
        }

        var totalCount = await query.CountAsync();

        // Join to opportunity and users for projection
        var projected = from p in query
                        join o in _context.Opportunities on p.NoticeId equals o.NoticeId into oppJoin
                        from o in oppJoin.DefaultIfEmpty()
                        join assignee in _context.AppUsers on p.AssignedTo equals assignee.UserId into aJoin
                        from assignee in aJoin.DefaultIfEmpty()
                        join cm in _context.AppUsers on p.CaptureManagerId equals cm.UserId into cmJoin
                        from cm in cmJoin.DefaultIfEmpty()
                        select new ProspectListDto
                        {
                            ProspectId = p.ProspectId,
                            NoticeId = p.NoticeId,
                            Source = p.Source,
                            Status = p.Status,
                            Priority = p.Priority,
                            GoNoGoScore = p.GoNoGoScore,
                            EstimatedValue = p.EstimatedValue,
                            AssignedToName = assignee != null ? assignee.DisplayName : null,
                            CaptureManagerName = cm != null ? cm.DisplayName : null,
                            OpportunityTitle = o != null ? o.Title : null,
                            ResponseDeadline = o != null ? o.ResponseDeadline : null,
                            SetAsideCode = o != null ? o.SetAsideCode : null,
                            NaicsCode = o != null ? o.NaicsCode : null,
                            DepartmentName = o != null ? o.DepartmentName : null,
                            Active = o != null ? o.Active : null,
                            CreatedAt = p.CreatedAt
                        };

        // Apply sorting
        if (!string.IsNullOrWhiteSpace(request.SortBy))
        {
            projected = request.SortBy.ToLowerInvariant() switch
            {
                "opportunitytitle" => request.SortDescending
                    ? projected.OrderByDescending(x => x.OpportunityTitle)
                    : projected.OrderBy(x => x.OpportunityTitle),
                "status" => request.SortDescending
                    ? projected.OrderByDescending(x => x.Status)
                    : projected.OrderBy(x => x.Status),
                "priority" => request.SortDescending
                    ? projected.OrderByDescending(x => x.Priority)
                    : projected.OrderBy(x => x.Priority),
                "gonogoscore" => request.SortDescending
                    ? projected.OrderByDescending(x => x.GoNoGoScore)
                    : projected.OrderBy(x => x.GoNoGoScore),
                "assignedtoname" => request.SortDescending
                    ? projected.OrderByDescending(x => x.AssignedToName)
                    : projected.OrderBy(x => x.AssignedToName),
                "estimatedvalue" => request.SortDescending
                    ? projected.OrderByDescending(x => x.EstimatedValue)
                    : projected.OrderBy(x => x.EstimatedValue),
                "responsedeadline" => request.SortDescending
                    ? projected.OrderByDescending(x => x.ResponseDeadline)
                    : projected.OrderBy(x => x.ResponseDeadline),
                "createdat" => request.SortDescending
                    ? projected.OrderByDescending(x => x.CreatedAt)
                    : projected.OrderBy(x => x.CreatedAt),
                _ => projected.OrderByDescending(x => x.CreatedAt)
            };
        }
        else
        {
            projected = projected.OrderByDescending(x => x.CreatedAt);
        }

        var items = await projected
            .Skip((request.Page - 1) * request.PageSize)
            .Take(request.PageSize)
            .ToListAsync();

        return new PagedResponse<ProspectListDto>
        {
            Items = items,
            Page = request.Page,
            PageSize = request.PageSize,
            TotalCount = totalCount
        };
    }

    public async Task<ProspectDetailDto?> GetDetailAsync(int organizationId, int prospectId)
    {
        var prospect = await _context.Prospects.AsNoTracking()
            .FirstOrDefaultAsync(p => p.ProspectId == prospectId && p.OrganizationId == organizationId);

        if (prospect == null) return null;

        // Fix 10: Consolidate related data retrieval. Notes and team members are fetched
        // with their joined data in a single query each (no per-note or per-member sub-queries).
        var opp = await _context.Opportunities.AsNoTracking()
            .FirstOrDefaultAsync(o => o.NoticeId == prospect.NoticeId);

        // Fetch assigned user and capture manager
        var assignedUser = prospect.AssignedTo.HasValue
            ? await _context.AppUsers.AsNoTracking()
                .FirstOrDefaultAsync(u => u.UserId == prospect.AssignedTo.Value)
            : null;

        var captureManager = prospect.CaptureManagerId.HasValue
            ? await _context.AppUsers.AsNoTracking()
                .FirstOrDefaultAsync(u => u.UserId == prospect.CaptureManagerId.Value)
            : null;

        // Fetch notes with user join in a single query
        var notes = await (from n in _context.ProspectNotes.AsNoTracking()
                           where n.ProspectId == prospectId
                           join u in _context.AppUsers on n.UserId equals u.UserId into uJoin
                           from u in uJoin.DefaultIfEmpty()
                           orderby n.CreatedAt ascending
                           select new ProspectNoteDto
                           {
                               NoteId = n.NoteId,
                               NoteType = n.NoteType,
                               NoteText = n.NoteText,
                               CreatedBy = u != null ? new UserSummaryDto
                               {
                                   UserId = u.UserId,
                                   DisplayName = u.DisplayName
                               } : null,
                               CreatedAt = n.CreatedAt
                           }).ToListAsync();

        // Fetch team members with entity join in a single query
        var teamMembers = await (from tm in _context.ProspectTeamMembers.AsNoTracking()
                                 where tm.ProspectId == prospectId
                                 join e in _context.Entities on tm.UeiSam equals e.UeiSam into eJoin
                                 from e in eJoin.DefaultIfEmpty()
                                 select new ProspectTeamMemberDto
                                 {
                                     Id = tm.Id,
                                     UeiSam = tm.UeiSam,
                                     EntityName = e != null ? e.LegalBusinessName : null,
                                     Role = tm.Role,
                                     Notes = tm.Notes,
                                     ProposedHourlyRate = tm.ProposedHourlyRate,
                                     CommitmentPct = tm.CommitmentPct
                                 }).ToListAsync();

        // Fetch proposal summary if exists
        var proposal = await _context.Proposals.AsNoTracking()
            .Where(pr => pr.ProspectId == prospectId)
            .Select(pr => new ProspectProposalSummaryDto
            {
                ProposalId = pr.ProposalId,
                ProposalStatus = pr.ProposalStatus,
                SubmissionDeadline = pr.SubmissionDeadline,
                SubmittedAt = pr.SubmittedAt,
                EstimatedValue = pr.EstimatedValue
            })
            .FirstOrDefaultAsync();

        // Score breakdown is only available via explicit POST /recalculate-score.
        // The cached GoNoGoScore is already returned in ProspectSummaryDto.
        ScoreBreakdownDto? scoreBreakdown = null;

        // Compose detail
        return new ProspectDetailDto
        {
            Prospect = new ProspectSummaryDto
            {
                ProspectId = prospect.ProspectId,
                NoticeId = prospect.NoticeId,
                Source = prospect.Source,
                Status = prospect.Status,
                Priority = prospect.Priority,
                GoNoGoScore = prospect.GoNoGoScore,
                WinProbability = prospect.WinProbability,
                EstimatedValue = prospect.EstimatedValue,
                EstimatedGrossMarginPct = prospect.EstimatedGrossMarginPct,
                BidSubmittedDate = prospect.BidSubmittedDate,
                Outcome = prospect.Outcome,
                OutcomeDate = prospect.OutcomeDate,
                OutcomeNotes = prospect.OutcomeNotes,
                CaptureManager = captureManager != null ? new UserSummaryDto
                {
                    UserId = captureManager.UserId,
                    DisplayName = captureManager.DisplayName
                } : null,
                AssignedTo = assignedUser != null ? new UserSummaryDto
                {
                    UserId = assignedUser.UserId,
                    DisplayName = assignedUser.DisplayName
                } : null,
                CreatedAt = prospect.CreatedAt,
                UpdatedAt = prospect.UpdatedAt
            },
            Opportunity = opp != null ? new ProspectOpportunityDto
            {
                Title = opp.Title,
                SolicitationNumber = opp.SolicitationNumber,
                DepartmentName = opp.DepartmentName,
                SubTier = opp.SubTier,
                Office = opp.Office,
                PostedDate = opp.PostedDate,
                ResponseDeadline = opp.ResponseDeadline,
                Type = opp.Type,
                SetAsideCode = opp.SetAsideCode,
                SetAsideDescription = opp.SetAsideDescription,
                NaicsCode = opp.NaicsCode,
                PopState = opp.PopState,
                PopZip = opp.PopZip,
                PopCountry = opp.PopCountry,
                Active = opp.Active,
                AwardAmount = opp.AwardAmount,
                Link = OpportunityService.NormalizeSamGovLink(opp.Link)
            } : null,
            Notes = notes,
            TeamMembers = teamMembers,
            Proposal = proposal,
            ScoreBreakdown = scoreBreakdown
        };
    }

    public async Task<ProspectDetailDto> UpdateStatusAsync(int organizationId, int prospectId, int userId, UpdateProspectStatusRequest request)
    {
        var prospect = await _context.Prospects
            .FirstOrDefaultAsync(p => p.ProspectId == prospectId && p.OrganizationId == organizationId)
            ?? throw new KeyNotFoundException($"Prospect {prospectId} not found");

        var currentStatus = prospect.Status;
        var newStatus = request.NewStatus;

        // Check terminal status
        if (TerminalStatuses.Contains(currentStatus))
            throw new InvalidOperationException($"Prospect {prospectId} is in terminal status '{currentStatus}' and cannot be updated");

        // Check valid transition
        if (!StatusFlow.TryGetValue(currentStatus, out var allowed) || !allowed.Contains(newStatus))
        {
            var allowedStr = StatusFlow.TryGetValue(currentStatus, out var a)
                ? string.Join(", ", a)
                : "none";
            throw new InvalidOperationException($"Invalid status transition: {currentStatus} -> {newStatus}. Allowed transitions: {allowedStr}");
        }

        // Update status
        prospect.Status = newStatus;

        // Terminal status handling
        if (TerminalStatuses.Contains(newStatus))
        {
            prospect.Outcome = newStatus;
            prospect.OutcomeDate = DateOnly.FromDateTime(DateTime.UtcNow);
            if (!string.IsNullOrEmpty(request.Notes))
                prospect.OutcomeNotes = request.Notes;
        }

        // BID_SUBMITTED handling
        if (newStatus == "BID_SUBMITTED")
        {
            prospect.BidSubmittedDate = DateOnly.FromDateTime(DateTime.UtcNow);
        }

        prospect.UpdatedAt = DateTime.UtcNow;

        // Auto-create STATUS_CHANGE note
        var noteText = $"Status changed: {currentStatus} -> {newStatus}.";
        if (!string.IsNullOrWhiteSpace(request.Notes))
            noteText += $" {request.Notes}";

        var note = new ProspectNote
        {
            ProspectId = prospectId,
            UserId = userId,
            NoteType = "STATUS_CHANGE",
            NoteText = noteText,
            CreatedAt = DateTime.UtcNow
        };

        _context.ProspectNotes.Add(note);
        await _context.SaveChangesAsync();

        // Log activity
        await _activityLog.LogAsync(organizationId, userId, "UPDATE_STATUS", "PROSPECT", prospectId.ToString(),
            new { OldStatus = currentStatus, NewStatus = newStatus });

        // Notify assigned user of status change
        if (prospect.AssignedTo.HasValue)
        {
            await _notificationService.CreateNotificationAsync(
                prospect.AssignedTo.Value,
                "STATUS_CHANGED",
                $"Prospect status changed to {newStatus}",
                $"Prospect for {prospect.NoticeId} changed from {currentStatus} to {newStatus}",
                "PROSPECT",
                prospect.ProspectId.ToString());
        }

        return (await GetDetailAsync(organizationId, prospectId))!;
    }

    public async Task<ProspectDetailDto> ReassignAsync(int organizationId, int prospectId, int userId, ReassignProspectRequest request)
    {
        var prospect = await _context.Prospects
            .FirstOrDefaultAsync(p => p.ProspectId == prospectId && p.OrganizationId == organizationId)
            ?? throw new KeyNotFoundException($"Prospect {prospectId} not found");

        // Validate new assignee is in the same organization
        var newAssignee = await _context.AppUsers.AsNoTracking()
            .FirstOrDefaultAsync(u => u.UserId == request.NewAssignedTo && u.OrganizationId == organizationId)
            ?? throw new InvalidOperationException($"User {request.NewAssignedTo} not found");

        if (newAssignee.IsActive != "Y")
            throw new InvalidOperationException($"User {request.NewAssignedTo} is not active");

        // Get old assignee username for note
        var oldAssigneeName = "unassigned";
        if (prospect.AssignedTo.HasValue)
        {
            var oldAssignee = await _context.AppUsers.AsNoTracking()
                .FirstOrDefaultAsync(u => u.UserId == prospect.AssignedTo.Value);
            if (oldAssignee != null)
                oldAssigneeName = oldAssignee.Username;
        }

        var newAssigneeName = newAssignee.Username;

        // Update
        prospect.AssignedTo = request.NewAssignedTo;
        prospect.UpdatedAt = DateTime.UtcNow;

        // Auto-create ASSIGNMENT note
        var noteText = $"Reassigned from {oldAssigneeName} to {newAssigneeName}.";
        if (!string.IsNullOrWhiteSpace(request.Notes))
            noteText += $" {request.Notes}";

        var note = new ProspectNote
        {
            ProspectId = prospectId,
            UserId = userId,
            NoteType = "ASSIGNMENT",
            NoteText = noteText,
            CreatedAt = DateTime.UtcNow
        };

        _context.ProspectNotes.Add(note);
        await _context.SaveChangesAsync();

        // Log activity
        await _activityLog.LogAsync(organizationId, userId, "REASSIGN_PROSPECT", "PROSPECT", prospectId.ToString(),
            new { OldAssignedTo = oldAssigneeName, NewAssignedTo = newAssigneeName });

        // Notify new assignee
        await _notificationService.CreateNotificationAsync(
            request.NewAssignedTo,
            "PROSPECT_ASSIGNED",
            "Prospect assigned to you",
            $"Prospect for opportunity {prospect.NoticeId} has been assigned to you",
            "PROSPECT",
            prospect.ProspectId.ToString());

        return (await GetDetailAsync(organizationId, prospectId))!;
    }

    public async Task<ProspectNoteDto> AddNoteAsync(int organizationId, int prospectId, int userId, CreateProspectNoteRequest request)
    {
        // Validate prospect exists and belongs to org
        var prospectExists = await _context.Prospects.AnyAsync(p => p.ProspectId == prospectId && p.OrganizationId == organizationId);
        if (!prospectExists)
            throw new KeyNotFoundException($"Prospect {prospectId} not found");

        // STATUS_CHANGE notes are system-only
        if (request.NoteType == "STATUS_CHANGE")
            throw new InvalidOperationException("STATUS_CHANGE notes are system-generated and cannot be created manually");

        var note = new ProspectNote
        {
            ProspectId = prospectId,
            UserId = userId,
            NoteType = request.NoteType,
            NoteText = request.NoteText,
            CreatedAt = DateTime.UtcNow
        };

        _context.ProspectNotes.Add(note);
        await _context.SaveChangesAsync();

        // Log activity
        await _activityLog.LogAsync(organizationId, userId, "ADD_NOTE", "PROSPECT", prospectId.ToString());

        // Return with user info
        var user = await _context.AppUsers.AsNoTracking()
            .FirstOrDefaultAsync(u => u.UserId == userId);

        return new ProspectNoteDto
        {
            NoteId = note.NoteId,
            NoteType = note.NoteType,
            NoteText = note.NoteText,
            CreatedBy = user != null ? new UserSummaryDto
            {
                UserId = user.UserId,
                DisplayName = user.DisplayName
            } : null,
            CreatedAt = note.CreatedAt
        };
    }

    public async Task<ProspectTeamMemberDto> AddTeamMemberAsync(int organizationId, int prospectId, int userId, AddTeamMemberRequest request)
    {
        // Validate prospect exists and belongs to org
        var prospectExists = await _context.Prospects.AnyAsync(p => p.ProspectId == prospectId && p.OrganizationId == organizationId);
        if (!prospectExists)
            throw new KeyNotFoundException($"Prospect {prospectId} not found");

        // Try to find entity name if UeiSam provided
        string? entityName = null;
        if (!string.IsNullOrWhiteSpace(request.UeiSam))
        {
            var entity = await _context.Entities.AsNoTracking()
                .FirstOrDefaultAsync(e => e.UeiSam == request.UeiSam);
            if (entity != null)
            {
                entityName = entity.LegalBusinessName;
            }
            else
            {
                _logger.LogWarning("Entity with UEI {UeiSam} not found in entity table", request.UeiSam);
            }
        }

        var teamMember = new ProspectTeamMember
        {
            ProspectId = prospectId,
            UeiSam = request.UeiSam,
            Role = request.Role,
            Notes = request.Notes,
            ProposedHourlyRate = request.ProposedHourlyRate,
            CommitmentPct = request.CommitmentPct
        };

        _context.ProspectTeamMembers.Add(teamMember);
        await _context.SaveChangesAsync();

        // Log activity
        await _activityLog.LogAsync(organizationId, userId, "ADD_TEAM_MEMBER", "PROSPECT", prospectId.ToString());

        return new ProspectTeamMemberDto
        {
            Id = teamMember.Id,
            UeiSam = teamMember.UeiSam,
            EntityName = entityName,
            Role = teamMember.Role,
            Notes = teamMember.Notes,
            ProposedHourlyRate = teamMember.ProposedHourlyRate,
            CommitmentPct = teamMember.CommitmentPct
        };
    }

    public async Task<bool> RemoveTeamMemberAsync(int organizationId, int prospectId, int memberId, int userId)
    {
        // Verify prospect belongs to org
        var prospectExists = await _context.Prospects.AnyAsync(p => p.ProspectId == prospectId && p.OrganizationId == organizationId);
        if (!prospectExists)
            return false;

        var member = await _context.ProspectTeamMembers
            .FirstOrDefaultAsync(tm => tm.Id == memberId && tm.ProspectId == prospectId);

        if (member == null)
            return false;

        _context.ProspectTeamMembers.Remove(member);
        await _context.SaveChangesAsync();

        // Log activity
        await _activityLog.LogAsync(organizationId, userId, "REMOVE_TEAM_MEMBER", "PROSPECT", prospectId.ToString());

        return true;
    }

    public async Task<ScoreBreakdownDto> RecalculateScoreAsync(int organizationId, int prospectId, int userId)
    {
        // Validate prospect exists and belongs to org
        var prospectExists = await _context.Prospects.AnyAsync(p => p.ProspectId == prospectId && p.OrganizationId == organizationId);
        if (!prospectExists)
            throw new KeyNotFoundException($"Prospect {prospectId} not found");

        var result = await _scoringService.CalculateScoreAsync(prospectId, organizationId);

        // Log activity
        await _activityLog.LogAsync(organizationId, userId, "RECALCULATE_SCORE", "PROSPECT", prospectId.ToString());

        return result;
    }
}
