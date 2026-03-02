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
        ILogger<ProspectService> logger)
    {
        _context = context;
        _scoringService = scoringService;
        _activityLog = activityLog;
        _logger = logger;
    }

    public async Task<ProspectDetailDto> CreateAsync(int userId, CreateProspectRequest request)
    {
        // Validate opportunity exists
        var oppExists = await _context.Opportunities.AnyAsync(o => o.NoticeId == request.NoticeId);
        if (!oppExists)
            throw new InvalidOperationException($"Opportunity with notice ID '{request.NoticeId}' not found");

        // Check for existing prospect
        var prospectExists = await _context.Prospects.AnyAsync(p => p.NoticeId == request.NoticeId);
        if (prospectExists)
            throw new InvalidOperationException($"A prospect already exists for opportunity '{request.NoticeId}'");

        // Validate assignee if provided
        if (request.AssignedTo.HasValue)
        {
            var assignee = await _context.AppUsers.AsNoTracking()
                .FirstOrDefaultAsync(u => u.UserId == request.AssignedTo.Value);
            if (assignee == null || assignee.IsActive != "Y")
                throw new InvalidOperationException($"User {request.AssignedTo.Value} not found or not active");
        }

        var priority = request.Priority ?? "MEDIUM";

        var prospect = new Prospect
        {
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
            await _scoringService.CalculateScoreAsync(prospect.ProspectId);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to calculate Go/No-Go score for prospect {ProspectId}", prospect.ProspectId);
        }

        // Log activity
        await _activityLog.LogAsync(userId, "CREATE_PROSPECT", "PROSPECT", prospect.ProspectId.ToString());

        return (await GetDetailAsync(prospect.ProspectId))!;
    }

    public async Task<PagedResponse<ProspectListDto>> SearchAsync(ProspectSearchRequest request)
    {
        var query = _context.Prospects.AsNoTracking().AsQueryable();

        // Apply filters
        if (!string.IsNullOrWhiteSpace(request.Status))
            query = query.Where(p => p.Status == request.Status);

        if (request.AssignedTo.HasValue)
            query = query.Where(p => p.AssignedTo == request.AssignedTo.Value);

        if (request.CaptureManagerId.HasValue)
            query = query.Where(p => p.CaptureManagerId == request.CaptureManagerId.Value);

        if (!string.IsNullOrWhiteSpace(request.Priority))
            query = query.Where(p => p.Priority == request.Priority);

        if (request.OpenOnly)
            query = query.Where(p => p.Status != "WON" && p.Status != "LOST" && p.Status != "DECLINED" && p.Status != "NO_BID");

        // NAICS filter: join to opportunity
        if (!string.IsNullOrWhiteSpace(request.Naics))
        {
            var naicsFilter = request.Naics;
            query = from p in query
                    join o in _context.Opportunities on p.NoticeId equals o.NoticeId
                    where o.NaicsCode != null && o.NaicsCode.StartsWith(naicsFilter)
                    select p;
        }

        // SetAside filter: join to opportunity
        if (!string.IsNullOrWhiteSpace(request.SetAside))
        {
            var setAsideFilter = request.SetAside;
            query = from p in query
                    join o in _context.Opportunities on p.NoticeId equals o.NoticeId
                    where o.SetAsideCode == setAsideFilter
                    select p;
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
                "responsedeadline" => request.SortDescending
                    ? projected.OrderByDescending(x => x.ResponseDeadline)
                    : projected.OrderBy(x => x.ResponseDeadline),
                "estimatedvalue" => request.SortDescending
                    ? projected.OrderByDescending(x => x.EstimatedValue)
                    : projected.OrderBy(x => x.EstimatedValue),
                "gonogoscore" => request.SortDescending
                    ? projected.OrderByDescending(x => x.GoNoGoScore)
                    : projected.OrderBy(x => x.GoNoGoScore),
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

    public async Task<ProspectDetailDto?> GetDetailAsync(int prospectId)
    {
        var prospect = await _context.Prospects.AsNoTracking()
            .FirstOrDefaultAsync(p => p.ProspectId == prospectId);

        if (prospect == null) return null;

        // Fetch linked opportunity
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

        // Fetch notes ordered by CreatedAt ASC, joined to AppUser
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

        // Fetch team members, left join to Entity for legal_business_name
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

        // Fetch proposal if exists
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
                Link = opp.Link
            } : null,
            Notes = notes,
            TeamMembers = teamMembers,
            Proposal = proposal,
            ScoreBreakdown = scoreBreakdown
        };
    }

    public async Task<ProspectDetailDto> UpdateStatusAsync(int prospectId, int userId, UpdateProspectStatusRequest request)
    {
        var prospect = await _context.Prospects
            .FirstOrDefaultAsync(p => p.ProspectId == prospectId)
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
        await _activityLog.LogAsync(userId, "UPDATE_STATUS", "PROSPECT", prospectId.ToString(),
            new { OldStatus = currentStatus, NewStatus = newStatus });

        return (await GetDetailAsync(prospectId))!;
    }

    public async Task<ProspectDetailDto> ReassignAsync(int prospectId, int userId, ReassignProspectRequest request)
    {
        var prospect = await _context.Prospects
            .FirstOrDefaultAsync(p => p.ProspectId == prospectId)
            ?? throw new KeyNotFoundException($"Prospect {prospectId} not found");

        // Validate new assignee
        var newAssignee = await _context.AppUsers.AsNoTracking()
            .FirstOrDefaultAsync(u => u.UserId == request.NewAssignedTo)
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
        await _activityLog.LogAsync(userId, "REASSIGN_PROSPECT", "PROSPECT", prospectId.ToString(),
            new { OldAssignedTo = oldAssigneeName, NewAssignedTo = newAssigneeName });

        return (await GetDetailAsync(prospectId))!;
    }

    public async Task<ProspectNoteDto> AddNoteAsync(int prospectId, int userId, CreateProspectNoteRequest request)
    {
        // Validate prospect exists
        var prospectExists = await _context.Prospects.AnyAsync(p => p.ProspectId == prospectId);
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
        await _activityLog.LogAsync(userId, "ADD_NOTE", "PROSPECT", prospectId.ToString());

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

    public async Task<ProspectTeamMemberDto> AddTeamMemberAsync(int prospectId, int userId, AddTeamMemberRequest request)
    {
        // Validate prospect exists
        var prospectExists = await _context.Prospects.AnyAsync(p => p.ProspectId == prospectId);
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
        await _activityLog.LogAsync(userId, "ADD_TEAM_MEMBER", "PROSPECT", prospectId.ToString());

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

    public async Task<bool> RemoveTeamMemberAsync(int prospectId, int memberId, int userId)
    {
        var member = await _context.ProspectTeamMembers
            .FirstOrDefaultAsync(tm => tm.Id == memberId && tm.ProspectId == prospectId);

        if (member == null)
            return false;

        _context.ProspectTeamMembers.Remove(member);
        await _context.SaveChangesAsync();

        // Log activity
        await _activityLog.LogAsync(userId, "REMOVE_TEAM_MEMBER", "PROSPECT", prospectId.ToString());

        return true;
    }

    public async Task<ScoreBreakdownDto> RecalculateScoreAsync(int prospectId, int userId)
    {
        // Validate prospect exists
        var prospectExists = await _context.Prospects.AnyAsync(p => p.ProspectId == prospectId);
        if (!prospectExists)
            throw new KeyNotFoundException($"Prospect {prospectId} not found");

        var result = await _scoringService.CalculateScoreAsync(prospectId);

        // Log activity
        await _activityLog.LogAsync(userId, "RECALCULATE_SCORE", "PROSPECT", prospectId.ToString());

        return result;
    }
}
