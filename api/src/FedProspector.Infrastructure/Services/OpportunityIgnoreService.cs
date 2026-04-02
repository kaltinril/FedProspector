using FedProspector.Core.Interfaces;
using FedProspector.Core.Models;
using FedProspector.Infrastructure.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;

namespace FedProspector.Infrastructure.Services;

public class OpportunityIgnoreService : IOpportunityIgnoreService
{
    private readonly FedProspectorDbContext _context;
    private readonly ILogger<OpportunityIgnoreService> _logger;

    public OpportunityIgnoreService(FedProspectorDbContext context, ILogger<OpportunityIgnoreService> logger)
    {
        _context = context;
        _logger = logger;
    }

    public async Task<OpportunityIgnore> IgnoreAsync(int userId, string noticeId, string? reason)
    {
        var existing = await _context.OpportunityIgnores
            .FirstOrDefaultAsync(i => i.UserId == userId && i.NoticeId == noticeId);

        if (existing != null)
            return existing;

        var ignore = new OpportunityIgnore
        {
            UserId = userId,
            NoticeId = noticeId,
            IgnoredAt = DateTime.UtcNow,
            Reason = reason
        };

        _context.OpportunityIgnores.Add(ignore);
        await _context.SaveChangesAsync();

        _logger.LogInformation("User {UserId} ignored opportunity {NoticeId}", userId, noticeId);
        return ignore;
    }

    public async Task UnignoreAsync(int userId, string noticeId)
    {
        var existing = await _context.OpportunityIgnores
            .FirstOrDefaultAsync(i => i.UserId == userId && i.NoticeId == noticeId);

        if (existing == null)
            return;

        _context.OpportunityIgnores.Remove(existing);
        await _context.SaveChangesAsync();

        _logger.LogInformation("User {UserId} un-ignored opportunity {NoticeId}", userId, noticeId);
    }

    public async Task<HashSet<string>> GetIgnoredNoticeIdsAsync(int userId)
    {
        var ids = await _context.OpportunityIgnores
            .Where(i => i.UserId == userId)
            .Select(i => i.NoticeId)
            .ToListAsync();

        return ids.ToHashSet();
    }

    public async Task<bool> IsIgnoredAsync(int userId, string noticeId)
    {
        return await _context.OpportunityIgnores
            .AnyAsync(i => i.UserId == userId && i.NoticeId == noticeId);
    }
}
