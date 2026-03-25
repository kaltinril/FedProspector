using System.Text.Json;
using FedProspector.Core.Constants;
using FedProspector.Core.DTOs.Prospects;
using FedProspector.Core.DTOs.SavedSearches;
using FedProspector.Core.Interfaces;
using FedProspector.Core.Models;
using FedProspector.Infrastructure.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;

namespace FedProspector.Infrastructure.Services;

public class AutoProspectService : IAutoProspectService
{
    private readonly FedProspectorDbContext _context;
    private readonly IPWinService _pwinService;
    private readonly INotificationService _notificationService;
    private readonly ILogger<AutoProspectService> _logger;

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        WriteIndented = false
    };

    public AutoProspectService(
        FedProspectorDbContext context,
        IPWinService pwinService,
        INotificationService notificationService,
        ILogger<AutoProspectService> logger)
    {
        _context = context;
        _pwinService = pwinService;
        _notificationService = notificationService;
        _logger = logger;
    }

    public async Task<AutoProspectResult> GenerateAutoProspectsAsync(int orgId)
    {
        var result = new AutoProspectResult();

        // Get org's saved searches where auto_prospect_enabled = 'Y'
        var searches = await _context.SavedSearches
            .Where(s => s.OrganizationId == orgId
                && s.AutoProspectEnabled == "Y"
                && s.IsActive == "Y")
            .ToListAsync();

        if (searches.Count == 0)
        {
            _logger.LogInformation("No auto-prospect enabled saved searches for org {OrgId}", orgId);
            return result;
        }

        var totalCreated = 0;
        decimal highestPwin = 0;

        foreach (var search in searches)
        {
            var searchResult = new AutoProspectSearchResult
            {
                SearchId = search.SearchId,
                SearchName = search.SearchName
            };

            try
            {
                var criteria = JsonSerializer.Deserialize<SavedSearchFilterCriteria>(
                    search.FilterCriteria, JsonOptions);
                if (criteria == null) continue;

                // Build candidate query — only open opportunities not already prospects
                var candidates = await GetCandidateNoticeIdsAsync(orgId, criteria);
                searchResult.Candidates = candidates.Count;
                result.Evaluated += candidates.Count;

                var minPwin = search.MinPwinScore ?? 30.0m;
                var searchCreated = 0;

                foreach (var noticeId in candidates)
                {
                    try
                    {
                        var pwin = await _pwinService.CalculateAsync(noticeId, orgId);

                        if ((decimal)pwin.Score >= minPwin)
                        {
                            var priority = pwin.Score >= 70 ? "HIGH"
                                : pwin.Score >= 40 ? "MEDIUM"
                                : "LOW";

                            var prospect = new Prospect
                            {
                                OrganizationId = orgId,
                                Source = "AUTO_MATCH",
                                NoticeId = noticeId,
                                AssignedTo = search.AutoAssignTo,
                                Status = "NEW",
                                Priority = priority,
                                WinProbability = (decimal)pwin.Score,
                                CreatedAt = DateTime.UtcNow,
                                UpdatedAt = DateTime.UtcNow
                            };

                            _context.Prospects.Add(prospect);
                            await _context.SaveChangesAsync();

                            // Auto-note
                            var note = new ProspectNote
                            {
                                ProspectId = prospect.ProspectId,
                                UserId = search.AutoAssignTo ?? search.UserId,
                                NoteType = "AUTO_MATCH",
                                NoteText = $"Auto-matched via saved search '{search.SearchName}': pWin {pwin.Score:F1}%, NAICS {pwin.Factors.FirstOrDefault(f => f.Name == "NAICS Experience")?.Detail ?? "N/A"}",
                                CreatedAt = DateTime.UtcNow
                            };
                            _context.ProspectNotes.Add(note);
                            await _context.SaveChangesAsync();

                            searchCreated++;
                            totalCreated++;
                            if ((decimal)pwin.Score > highestPwin)
                                highestPwin = (decimal)pwin.Score;

                            result.Created++;
                        }
                        else
                        {
                            result.Skipped++;
                        }
                    }
                    catch (Exception ex)
                    {
                        _logger.LogWarning(ex, "Error scoring opportunity {NoticeId} for auto-prospect", noticeId);
                        result.Errors.Add($"Error scoring {noticeId}: {ex.Message}");
                    }
                }

                // Update saved search tracking
                search.LastAutoRunAt = DateTime.UtcNow;
                search.LastAutoCreated = searchCreated;
                search.UpdatedAt = DateTime.UtcNow;
                await _context.SaveChangesAsync();

                searchResult.Created = searchCreated;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error running auto-prospect for saved search {SearchId}", search.SearchId);
                result.Errors.Add($"Search '{search.SearchName}': {ex.Message}");
            }

            result.SearchResults.Add(searchResult);
        }

        // Create summary notification
        if (totalCreated > 0)
        {
            // Notify org owner/admins
            var adminUsers = await _context.AppUsers.AsNoTracking()
                .Where(u => u.OrganizationId == orgId && u.IsActive == "Y"
                    && (u.OrgRole == "owner" || u.IsOrgAdmin == "Y"))
                .Select(u => u.UserId)
                .ToListAsync();

            foreach (var adminId in adminUsers)
            {
                await _notificationService.CreateNotificationAsync(
                    adminId,
                    "AUTO_PROSPECT",
                    $"Auto-prospect: {totalCreated} new prospects",
                    $"Auto-prospect run completed: {totalCreated} new prospects from {searches.Count} saved searches. Highest pWin: {highestPwin:F0}%.",
                    "PROSPECT",
                    null);
            }
        }

        _logger.LogInformation(
            "Auto-prospect completed for org {OrgId}: evaluated {Evaluated}, created {Created}, skipped {Skipped}",
            orgId, result.Evaluated, result.Created, result.Skipped);

        return result;
    }

    public async Task<AutoProspectResult> GenerateRecompeteProspectsAsync(int orgId)
    {
        var result = new AutoProspectResult();

        // Get org's NAICS codes
        var orgNaics = await _context.OrganizationNaics.AsNoTracking()
            .Where(n => n.OrganizationId == orgId)
            .Select(n => n.NaicsCode)
            .ToListAsync();

        if (orgNaics.Count == 0) return result;

        // Find expiring contracts with matching follow-on solicitations
        var now = DateOnly.FromDateTime(DateTime.UtcNow);
        var cutoff = now.AddMonths(12);

        // Stage 1: Get expiring FPDS contracts in org's NAICS codes
        var fpdsContracts = await _context.FpdsContracts.AsNoTracking()
            .Where(c => c.ModificationNumber == "0"
                && c.UltimateCompletionDate != null
                && c.UltimateCompletionDate >= now
                && c.UltimateCompletionDate <= cutoff
                && c.NaicsCode != null
                && orgNaics.Contains(c.NaicsCode))
            .Select(c => new { c.SolicitationNumber, c.NaicsCode, c.FundingAgencyName })
            .Distinct()
            .ToListAsync();

        _logger.LogInformation("Recompete: {Count} expiring FPDS contracts for org {OrgId}", fpdsContracts.Count, orgId);

        // Collect FPDS solicitation numbers for dedup against USASpending
        var fpdsSolicitations = new HashSet<string>(
            fpdsContracts
                .Where(c => !string.IsNullOrEmpty(c.SolicitationNumber))
                .Select(c => c.SolicitationNumber!),
            StringComparer.OrdinalIgnoreCase);

        // Stage 2: Get expiring USASpending awards in org's NAICS codes (contracts only, deduped)
        var usaContracts = await _context.UsaspendingAwards.AsNoTracking()
            .Where(a => a.DeletedAt == null
                && a.Piid != null
                && a.EndDate != null
                && a.EndDate >= now
                && a.EndDate <= cutoff
                && a.NaicsCode != null
                && orgNaics.Contains(a.NaicsCode))
            .Select(a => new { a.SolicitationIdentifier, a.NaicsCode, a.FundingAgencyName, a.AwardingAgencyName })
            .Distinct()
            .ToListAsync();

        // Dedup: exclude USASpending rows whose solicitation already appeared in FPDS
        var usaContractsDeduped = usaContracts
            .Where(a => string.IsNullOrEmpty(a.SolicitationIdentifier)
                || !fpdsSolicitations.Contains(a.SolicitationIdentifier))
            .ToList();

        _logger.LogInformation("Recompete: {Count} expiring USASpending contracts for org {OrgId} ({Excluded} deduped)",
            usaContractsDeduped.Count, orgId, usaContracts.Count - usaContractsDeduped.Count);

        // Combine both sources into a unified list
        var expiringContracts = fpdsContracts
            .Select(c => new { SolicitationNumber = c.SolicitationNumber, NaicsCode = c.NaicsCode, FundingAgencyName = c.FundingAgencyName })
            .Concat(usaContractsDeduped
                .Select(a => new { SolicitationNumber = a.SolicitationIdentifier, NaicsCode = a.NaicsCode, FundingAgencyName = a.FundingAgencyName ?? a.AwardingAgencyName }))
            .ToList();

        foreach (var contract in expiringContracts)
        {
            result.Evaluated++;

            // Try to match to an existing opportunity
            string? matchedNoticeId = null;

            // Match by solicitation number first
            if (!string.IsNullOrEmpty(contract.SolicitationNumber))
            {
                matchedNoticeId = await _context.Opportunities.AsNoTracking()
                    .Where(o => o.SolicitationNumber == contract.SolicitationNumber
                        && o.Active == "Y"
                        && !OpportunityFilters.NonBiddableTypes.Contains(o.Type!)
                        && o.ResponseDeadline != null
                        && o.ResponseDeadline > DateTime.UtcNow)
                    .Select(o => o.NoticeId)
                    .FirstOrDefaultAsync();
            }

            // Match by agency + NAICS pattern
            if (matchedNoticeId == null && !string.IsNullOrEmpty(contract.FundingAgencyName))
            {
                matchedNoticeId = await _context.Opportunities.AsNoTracking()
                    .Where(o => o.DepartmentName == contract.FundingAgencyName
                        && o.NaicsCode == contract.NaicsCode
                        && o.Active == "Y"
                        && !OpportunityFilters.NonBiddableTypes.Contains(o.Type!)
                        && o.ResponseDeadline != null
                        && o.ResponseDeadline > DateTime.UtcNow)
                    .Select(o => o.NoticeId)
                    .FirstOrDefaultAsync();
            }

            if (matchedNoticeId == null)
            {
                result.Skipped++;
                continue;
            }

            // Check if prospect already exists
            var exists = await _context.Prospects.AnyAsync(
                p => p.OrganizationId == orgId && p.NoticeId == matchedNoticeId);
            if (exists)
            {
                result.Skipped++;
                continue;
            }

            try
            {
                var pwin = await _pwinService.CalculateAsync(matchedNoticeId, orgId);
                var priority = pwin.Score >= 70 ? "HIGH"
                    : pwin.Score >= 40 ? "MEDIUM"
                    : "LOW";

                var prospect = new Prospect
                {
                    OrganizationId = orgId,
                    Source = "AUTO_RECOMPETE",
                    NoticeId = matchedNoticeId,
                    Status = "NEW",
                    Priority = priority,
                    WinProbability = (decimal)pwin.Score,
                    CreatedAt = DateTime.UtcNow,
                    UpdatedAt = DateTime.UtcNow
                };

                _context.Prospects.Add(prospect);
                await _context.SaveChangesAsync();

                var note = new ProspectNote
                {
                    ProspectId = prospect.ProspectId,
                    NoteType = "AUTO_RECOMPETE",
                    NoteText = $"Auto-generated from expiring contract recompete. Solicitation: {contract.SolicitationNumber ?? "N/A"}, pWin: {pwin.Score:F1}%",
                    CreatedAt = DateTime.UtcNow
                };
                _context.ProspectNotes.Add(note);
                await _context.SaveChangesAsync();

                result.Created++;
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "Error creating recompete prospect for {NoticeId}", matchedNoticeId);
                result.Errors.Add($"Error for {matchedNoticeId}: {ex.Message}");
            }
        }

        _logger.LogInformation(
            "Recompete detection for org {OrgId}: evaluated {Evaluated}, created {Created}, skipped {Skipped}",
            orgId, result.Evaluated, result.Created, result.Skipped);

        return result;
    }

    private async Task<List<string>> GetCandidateNoticeIdsAsync(int orgId, SavedSearchFilterCriteria criteria)
    {
        IQueryable<Opportunity> query = _context.Opportunities.AsNoTracking();

        // Must be open
        query = query.Where(o => o.ResponseDeadline != null && o.ResponseDeadline > DateTime.UtcNow);
        query = query.Where(o => o.Active == "Y");

        // Apply saved search filters
        if (criteria.SetAsideCodes?.Count > 0)
            query = query.Where(o => criteria.SetAsideCodes.Contains(o.SetAsideCode!));

        if (criteria.NaicsCodes?.Count > 0)
            query = query.Where(o => criteria.NaicsCodes.Contains(o.NaicsCode!));

        if (criteria.States?.Count > 0)
            query = query.Where(o => criteria.States.Contains(o.PopState!));

        if (criteria.MinAwardAmount.HasValue)
            query = query.Where(o => o.AwardAmount >= criteria.MinAwardAmount);

        if (criteria.MaxAwardAmount.HasValue)
            query = query.Where(o => o.AwardAmount <= criteria.MaxAwardAmount);

        // Mandatory: exclude non-biddable notice types
        query = query.Where(o => !OpportunityFilters.NonBiddableTypes.Contains(o.Type!));

        if (criteria.Types?.Count > 0)
            query = query.Where(o => criteria.Types.Contains(o.Type!));

        if (criteria.DaysBack.HasValue)
        {
            var cutoff = DateOnly.FromDateTime(DateTime.UtcNow.AddDays(-criteria.DaysBack.Value));
            query = query.Where(o => o.PostedDate >= cutoff);
        }

        // Dedup: keep latest notice per solicitation
        query = query.Where(o =>
            (o.SolicitationNumber == null || o.SolicitationNumber == "") ||
            o.PostedDate == _context.Opportunities
                .Where(o2 => o2.SolicitationNumber == o.SolicitationNumber
                           && !OpportunityFilters.NonBiddableTypes.Contains(o2.Type!))
                .Max(o2 => o2.PostedDate));

        // Dedup: exclude opportunities that already have a prospect for this org
        var existingNoticeIds = _context.Prospects
            .Where(p => p.OrganizationId == orgId)
            .Select(p => p.NoticeId);

        query = query.Where(o => !existingNoticeIds.Contains(o.NoticeId));

        // Limit to top 500 candidates ordered by response deadline
        return await query
            .OrderBy(o => o.ResponseDeadline)
            .Take(500)
            .Select(o => o.NoticeId)
            .ToListAsync();
    }
}
