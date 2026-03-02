using FedProspector.Core.DTOs.Proposals;
using FedProspector.Core.Exceptions;
using FedProspector.Core.Interfaces;
using FedProspector.Core.Models;
using FedProspector.Infrastructure.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;

namespace FedProspector.Infrastructure.Services;

public class ProposalService : IProposalService
{
    private readonly FedProspectorDbContext _context;
    private readonly IActivityLogService _activityLog;
    private readonly ILogger<ProposalService> _logger;

    private static readonly Dictionary<string, string[]> ProposalStatusFlow = new()
    {
        ["DRAFT"] = new[] { "IN_REVIEW", "CANCELLED" },
        ["IN_REVIEW"] = new[] { "SUBMITTED", "DRAFT", "CANCELLED" },
        ["SUBMITTED"] = new[] { "UNDER_EVALUATION", "CANCELLED" },
        ["UNDER_EVALUATION"] = new[] { "AWARDED", "NOT_AWARDED" },
    };

    private static readonly HashSet<string> TerminalProposalStatuses = new()
    {
        "AWARDED", "NOT_AWARDED", "CANCELLED"
    };

    private static readonly HashSet<string> ProspectTerminalStatuses = new()
    {
        "WON", "LOST", "DECLINED", "NO_BID"
    };

    private static readonly string[] DefaultMilestoneNames =
    {
        "Draft Due", "Internal Review", "Final Submission", "Q&A Period", "Award Decision"
    };

    public ProposalService(
        FedProspectorDbContext context,
        IActivityLogService activityLog,
        ILogger<ProposalService> logger)
    {
        _context = context;
        _activityLog = activityLog;
        _logger = logger;
    }

    public async Task<ProposalDetailDto> CreateAsync(int userId, CreateProposalRequest request)
    {
        // Validate prospect exists
        var prospect = await _context.Prospects
            .FirstOrDefaultAsync(p => p.ProspectId == request.ProspectId);

        if (prospect == null)
            throw new KeyNotFoundException($"Prospect {request.ProspectId} not found");

        // Check no existing proposal for this prospect (UNIQUE constraint)
        var exists = await _context.Proposals
            .AnyAsync(p => p.ProspectId == request.ProspectId);

        if (exists)
            throw new InvalidOperationException($"A proposal already exists for prospect {request.ProspectId}");

        // Create proposal entity
        var proposal = new Proposal
        {
            ProspectId = request.ProspectId,
            ProposalStatus = "DRAFT",
            SubmissionDeadline = request.SubmissionDeadline,
            EstimatedValue = request.EstimatedValue,
            CreatedAt = DateTime.UtcNow,
            UpdatedAt = DateTime.UtcNow
        };

        _context.Proposals.Add(proposal);
        await _context.SaveChangesAsync();

        // Sync proposal status to prospect
        prospect.ProposalStatus = "DRAFT";
        prospect.UpdatedAt = DateTime.UtcNow;

        // Auto-create default milestones
        foreach (var name in DefaultMilestoneNames)
        {
            _context.ProposalMilestones.Add(new ProposalMilestone
            {
                ProposalId = proposal.ProposalId,
                MilestoneName = name,
                Status = "PENDING",
                CreatedAt = DateTime.UtcNow
            });
        }

        await _context.SaveChangesAsync();

        // Log activity
        await _activityLog.LogAsync(userId, "CREATE_PROPOSAL", "PROPOSAL",
            proposal.ProposalId.ToString(),
            new { proposal.ProspectId, proposal.ProposalStatus });

        return await BuildDetailAsync(proposal.ProposalId);
    }

    public async Task<ProposalDetailDto> UpdateAsync(int proposalId, int userId, UpdateProposalRequest request)
    {
        var proposal = await _context.Proposals
            .FirstOrDefaultAsync(p => p.ProposalId == proposalId);

        if (proposal == null)
            throw new KeyNotFoundException($"Proposal {proposalId} not found");

        var details = new Dictionary<string, object?>();

        // Handle status update
        if (!string.IsNullOrEmpty(request.Status))
        {
            var currentStatus = proposal.ProposalStatus;
            var newStatus = request.Status;

            // Check terminal status
            if (TerminalProposalStatuses.Contains(currentStatus))
                throw new InvalidOperationException(
                    $"Proposal {proposalId} is in terminal status '{currentStatus}' and cannot be updated");

            // Validate transition
            if (!ProposalStatusFlow.TryGetValue(currentStatus, out var allowed) ||
                !allowed.Contains(newStatus))
            {
                var allowedStr = ProposalStatusFlow.TryGetValue(currentStatus, out var a)
                    ? string.Join(", ", a)
                    : "none";
                throw new InvalidOperationException(
                    $"Invalid proposal status transition: {currentStatus} -> {newStatus}. Allowed transitions: {allowedStr}");
            }

            // Prerequisite check for SUBMITTED
            if (newStatus == "SUBMITTED")
            {
                var prospect = await _context.Prospects
                    .FirstOrDefaultAsync(p => p.ProspectId == proposal.ProspectId);

                if (prospect == null)
                    throw new KeyNotFoundException($"Prospect {proposal.ProspectId} not found");

                if (prospect.Status != "BID_SUBMITTED")
                    throw new ConflictException(
                        $"Cannot submit proposal: prospect must be at BID_SUBMITTED status (currently '{prospect.Status}'). Advance the prospect status first.");
            }

            details["oldStatus"] = currentStatus;
            details["newStatus"] = newStatus;

            proposal.ProposalStatus = newStatus;

            if (newStatus == "SUBMITTED")
                proposal.SubmittedAt = DateTime.UtcNow;

            // Prospect auto-sync
            await SyncProspectOnStatusChange(proposal.ProspectId, currentStatus, newStatus, userId);
        }

        // Update other fields if provided
        if (request.EstimatedValue.HasValue)
        {
            details["oldEstimatedValue"] = proposal.EstimatedValue;
            details["newEstimatedValue"] = request.EstimatedValue;
            proposal.EstimatedValue = request.EstimatedValue;
        }

        if (request.WinProbabilityPct.HasValue)
        {
            details["oldWinProbabilityPct"] = proposal.WinProbabilityPct;
            details["newWinProbabilityPct"] = request.WinProbabilityPct;
            proposal.WinProbabilityPct = request.WinProbabilityPct;
        }

        proposal.UpdatedAt = DateTime.UtcNow;
        await _context.SaveChangesAsync();

        // Log activity
        await _activityLog.LogAsync(userId, "UPDATE_PROPOSAL", "PROPOSAL",
            proposalId.ToString(), details);

        return await BuildDetailAsync(proposalId);
    }

    public async Task<ProposalDocumentDto> AddDocumentAsync(int proposalId, int userId, AddProposalDocumentRequest request)
    {
        var proposalExists = await _context.Proposals
            .AnyAsync(p => p.ProposalId == proposalId);

        if (!proposalExists)
            throw new KeyNotFoundException($"Proposal {proposalId} not found");

        var document = new ProposalDocument
        {
            ProposalId = proposalId,
            DocumentType = request.DocumentType,
            FileName = request.FileName,
            FilePath = "",  // placeholder - file storage not implemented yet
            FileSizeBytes = request.FileSizeBytes,
            UploadedBy = userId,
            UploadedAt = DateTime.UtcNow,
            Notes = request.Notes
        };

        _context.ProposalDocuments.Add(document);
        await _context.SaveChangesAsync();

        // Log activity
        await _activityLog.LogAsync(userId, "UPLOAD_DOCUMENT", "PROPOSAL",
            proposalId.ToString(),
            new { document.DocumentId, document.FileName, document.DocumentType });

        return new ProposalDocumentDto
        {
            DocumentId = document.DocumentId,
            DocumentType = document.DocumentType,
            FileName = document.FileName,
            FileSizeBytes = document.FileSizeBytes,
            UploadedBy = document.UploadedBy,
            UploadedAt = document.UploadedAt,
            Notes = document.Notes
        };
    }

    public async Task<IEnumerable<ProposalMilestoneDto>> GetMilestonesAsync(int proposalId)
    {
        var proposalExists = await _context.Proposals
            .AnyAsync(p => p.ProposalId == proposalId);

        if (!proposalExists)
            throw new KeyNotFoundException($"Proposal {proposalId} not found");

        return await _context.ProposalMilestones.AsNoTracking()
            .Where(m => m.ProposalId == proposalId)
            .OrderBy(m => m.DueDate)
            .ThenBy(m => m.MilestoneId)
            .Select(m => new ProposalMilestoneDto
            {
                MilestoneId = m.MilestoneId,
                MilestoneName = m.MilestoneName,
                DueDate = m.DueDate,
                CompletedDate = m.CompletedDate,
                AssignedTo = m.AssignedTo,
                Status = m.Status,
                Notes = m.Notes,
                CreatedAt = m.CreatedAt
            })
            .ToListAsync();
    }

    public async Task<ProposalMilestoneDto> UpdateMilestoneAsync(
        int proposalId, int milestoneId, int userId, UpdateMilestoneRequest request)
    {
        var milestone = await _context.ProposalMilestones
            .FirstOrDefaultAsync(m => m.MilestoneId == milestoneId && m.ProposalId == proposalId);

        if (milestone == null)
            throw new KeyNotFoundException($"Milestone {milestoneId} not found for proposal {proposalId}");

        if (request.CompletedDate.HasValue)
            milestone.CompletedDate = request.CompletedDate;

        if (!string.IsNullOrEmpty(request.Status))
            milestone.Status = request.Status;

        if (request.Notes != null)
            milestone.Notes = request.Notes;

        await _context.SaveChangesAsync();

        // Log activity
        await _activityLog.LogAsync(userId, "UPDATE_MILESTONE", "PROPOSAL",
            proposalId.ToString(),
            new { milestoneId, milestone.MilestoneName, milestone.Status });

        return new ProposalMilestoneDto
        {
            MilestoneId = milestone.MilestoneId,
            MilestoneName = milestone.MilestoneName,
            DueDate = milestone.DueDate,
            CompletedDate = milestone.CompletedDate,
            AssignedTo = milestone.AssignedTo,
            Status = milestone.Status,
            Notes = milestone.Notes,
            CreatedAt = milestone.CreatedAt
        };
    }

    // -------------------------------------------------------------------
    // Private Helpers
    // -------------------------------------------------------------------

    private async Task SyncProspectOnStatusChange(int prospectId, string oldProposalStatus, string newProposalStatus, int userId)
    {
        var prospect = await _context.Prospects
            .FirstOrDefaultAsync(p => p.ProspectId == prospectId);

        if (prospect == null)
            return;

        if (ProspectTerminalStatuses.Contains(prospect.Status))
        {
            _logger.LogWarning("Prospect {ProspectId} already in terminal status {Status}, skipping auto-sync",
                prospect.ProspectId, prospect.Status);
            return;
        }

        switch (newProposalStatus)
        {
            case "AWARDED":
            {
                var oldStatus = prospect.Status;
                prospect.Status = "WON";
                prospect.Outcome = "WON";
                prospect.OutcomeDate = DateOnly.FromDateTime(DateTime.UtcNow);
                prospect.ProposalStatus = "AWARDED";
                prospect.UpdatedAt = DateTime.UtcNow;

                // Auto-create STATUS_CHANGE note
                _context.ProspectNotes.Add(new ProspectNote
                {
                    ProspectId = prospectId,
                    UserId = userId,
                    NoteType = "STATUS_CHANGE",
                    NoteText = $"Status changed: {oldStatus} -> WON. Proposal awarded.",
                    CreatedAt = DateTime.UtcNow
                });
                break;
            }
            case "NOT_AWARDED":
            {
                var oldStatus = prospect.Status;
                prospect.Status = "LOST";
                prospect.Outcome = "LOST";
                prospect.OutcomeDate = DateOnly.FromDateTime(DateTime.UtcNow);
                prospect.ProposalStatus = "NOT_AWARDED";
                prospect.UpdatedAt = DateTime.UtcNow;

                // Auto-create STATUS_CHANGE note
                _context.ProspectNotes.Add(new ProspectNote
                {
                    ProspectId = prospectId,
                    UserId = userId,
                    NoteType = "STATUS_CHANGE",
                    NoteText = $"Status changed: {oldStatus} -> LOST. Proposal not awarded.",
                    CreatedAt = DateTime.UtcNow
                });
                break;
            }
            case "CANCELLED":
                prospect.ProposalStatus = "CANCELLED";
                prospect.UpdatedAt = DateTime.UtcNow;
                break;

            default:
                // Non-terminal status changes: sync proposal status
                prospect.ProposalStatus = newProposalStatus;
                prospect.UpdatedAt = DateTime.UtcNow;
                break;
        }
    }

    private async Task<ProposalDetailDto> BuildDetailAsync(int proposalId)
    {
        var proposal = await _context.Proposals.AsNoTracking()
            .FirstOrDefaultAsync(p => p.ProposalId == proposalId);

        if (proposal == null)
            throw new KeyNotFoundException($"Proposal {proposalId} not found");

        var milestones = await _context.ProposalMilestones.AsNoTracking()
            .Where(m => m.ProposalId == proposalId)
            .OrderBy(m => m.DueDate)
            .ThenBy(m => m.MilestoneId)
            .Select(m => new ProposalMilestoneDto
            {
                MilestoneId = m.MilestoneId,
                MilestoneName = m.MilestoneName,
                DueDate = m.DueDate,
                CompletedDate = m.CompletedDate,
                AssignedTo = m.AssignedTo,
                Status = m.Status,
                Notes = m.Notes,
                CreatedAt = m.CreatedAt
            })
            .ToListAsync();

        var documents = await _context.ProposalDocuments.AsNoTracking()
            .Where(d => d.ProposalId == proposalId)
            .OrderByDescending(d => d.UploadedAt)
            .Select(d => new ProposalDocumentDto
            {
                DocumentId = d.DocumentId,
                DocumentType = d.DocumentType,
                FileName = d.FileName,
                FileSizeBytes = d.FileSizeBytes,
                UploadedBy = d.UploadedBy,
                UploadedAt = d.UploadedAt,
                Notes = d.Notes
            })
            .ToListAsync();

        return new ProposalDetailDto
        {
            ProposalId = proposal.ProposalId,
            ProspectId = proposal.ProspectId,
            ProposalNumber = proposal.ProposalNumber,
            ProposalStatus = proposal.ProposalStatus,
            SubmissionDeadline = proposal.SubmissionDeadline,
            SubmittedAt = proposal.SubmittedAt,
            EstimatedValue = proposal.EstimatedValue,
            WinProbabilityPct = proposal.WinProbabilityPct,
            LessonsLearned = proposal.LessonsLearned,
            Milestones = milestones,
            Documents = documents,
            CreatedAt = proposal.CreatedAt,
            UpdatedAt = proposal.UpdatedAt
        };
    }
}
