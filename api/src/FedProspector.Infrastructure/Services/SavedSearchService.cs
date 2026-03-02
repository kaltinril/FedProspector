using System.Text.Json;
using AutoMapper;
using FedProspector.Core.DTOs.Opportunities;
using FedProspector.Core.DTOs.SavedSearches;
using FedProspector.Core.Interfaces;
using FedProspector.Core.Models;
using FedProspector.Infrastructure.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;

namespace FedProspector.Infrastructure.Services;

public class SavedSearchService : ISavedSearchService
{
    private readonly FedProspectorDbContext _context;
    private readonly IMapper _mapper;
    private readonly INotificationService _notificationService;
    private readonly ILogger<SavedSearchService> _logger;

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        WriteIndented = false
    };

    public SavedSearchService(FedProspectorDbContext context, IMapper mapper, INotificationService notificationService, ILogger<SavedSearchService> logger)
    {
        _context = context;
        _mapper = mapper;
        _notificationService = notificationService;
        _logger = logger;
    }

    public async Task<IEnumerable<SavedSearchDto>> ListAsync(int userId)
    {
        // Saved searches are user-scoped; org scoping is implicit via user ownership
        var searches = await _context.SavedSearches.AsNoTracking()
            .Where(s => s.UserId == userId && s.IsActive == "Y")
            .OrderBy(s => s.SearchName)
            .ToListAsync();

        return _mapper.Map<IEnumerable<SavedSearchDto>>(searches);
    }

    public async Task<SavedSearchDto> CreateAsync(int userId, int organizationId, CreateSavedSearchRequest request)
    {
        var search = new SavedSearch
        {
            OrganizationId = organizationId,
            UserId = userId,
            SearchName = request.SearchName,
            Description = request.Description,
            FilterCriteria = JsonSerializer.Serialize(request.FilterCriteria, JsonOptions),
            NotificationEnabled = request.NotificationEnabled ? "Y" : "N",
            IsActive = "Y",
            CreatedAt = DateTime.UtcNow,
            UpdatedAt = DateTime.UtcNow
        };

        _context.SavedSearches.Add(search);
        await _context.SaveChangesAsync();

        return _mapper.Map<SavedSearchDto>(search);
    }

    public async Task<SavedSearchRunResultDto?> RunAsync(int userId, int searchId)
    {
        var search = await _context.SavedSearches
            .FirstOrDefaultAsync(s => s.SearchId == searchId && s.UserId == userId && s.IsActive == "Y");

        if (search == null) return null;

        var criteria = JsonSerializer.Deserialize<SavedSearchFilterCriteria>(search.FilterCriteria, JsonOptions);
        if (criteria == null) return null;

        // Build dynamic query
        IQueryable<Opportunity> query = _context.Opportunities.AsNoTracking();

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

        if (criteria.OpenOnly)
        {
            query = query.Where(o => o.Active == "Y");
            query = query.Where(o => o.ResponseDeadline != null && o.ResponseDeadline > DateTime.UtcNow);
        }

        if (criteria.Types?.Count > 0)
            query = query.Where(o => criteria.Types.Contains(o.Type!));

        if (criteria.DaysBack.HasValue)
        {
            var cutoff = DateOnly.FromDateTime(DateTime.UtcNow.AddDays(-criteria.DaysBack.Value));
            query = query.Where(o => o.PostedDate >= cutoff);
        }

        // Execute and get results (limit 200)
        var results = await query
            .OrderBy(o => o.ResponseDeadline)
            .Take(200)
            .Select(o => new OpportunitySearchDto
            {
                NoticeId = o.NoticeId,
                Title = o.Title,
                SolicitationNumber = o.SolicitationNumber,
                DepartmentName = o.DepartmentName,
                Office = o.Office,
                PostedDate = o.PostedDate,
                ResponseDeadline = o.ResponseDeadline,
                SetAsideCode = o.SetAsideCode,
                SetAsideDescription = o.SetAsideDescription,
                NaicsCode = o.NaicsCode,
                PopState = o.PopState,
                PopCity = o.PopCity
            })
            .ToListAsync();

        // Count new results (loaded since last run)
        var newCount = 0;
        if (search.LastRunAt.HasValue)
        {
            newCount = await query
                .CountAsync(o => o.FirstLoadedAt > search.LastRunAt.Value);
        }

        // Update last run time
        search.LastRunAt = DateTime.UtcNow;
        search.LastNewResults = newCount;
        search.UpdatedAt = DateTime.UtcNow;
        await _context.SaveChangesAsync();

        // Notify user of new search results
        if (newCount > 0 && search.NotificationEnabled == "Y")
        {
            await _notificationService.CreateNotificationAsync(
                search.UserId,
                "SEARCH_RESULTS",
                $"{newCount} new results for '{search.SearchName}'",
                $"Your saved search '{search.SearchName}' found {newCount} new opportunities",
                "SAVED_SEARCH",
                search.SearchId.ToString());
        }

        return new SavedSearchRunResultDto
        {
            SearchId = search.SearchId,
            SearchName = search.SearchName,
            Results = results,
            TotalCount = results.Count,
            NewCount = newCount,
            ExecutedAt = DateTime.UtcNow
        };
    }

    public async Task<bool> DeleteAsync(int userId, int searchId)
    {
        var search = await _context.SavedSearches
            .FirstOrDefaultAsync(s => s.SearchId == searchId && s.UserId == userId);

        if (search == null) return false;

        search.IsActive = "N";
        search.UpdatedAt = DateTime.UtcNow;
        await _context.SaveChangesAsync();

        return true;
    }

    public async Task<SavedSearchDto?> UpdateAsync(int userId, int searchId, UpdateSavedSearchRequest request)
    {
        var search = await _context.SavedSearches
            .FirstOrDefaultAsync(s => s.SearchId == searchId && s.UserId == userId && s.IsActive == "Y");

        if (search == null) return null;

        if (request.Name != null)
            search.SearchName = request.Name;

        if (request.Description != null)
            search.Description = request.Description;

        if (request.FilterCriteria != null)
            search.FilterCriteria = request.FilterCriteria;

        if (request.NotificationsEnabled.HasValue)
            search.NotificationEnabled = request.NotificationsEnabled.Value ? "Y" : "N";

        search.UpdatedAt = DateTime.UtcNow;
        await _context.SaveChangesAsync();

        return _mapper.Map<SavedSearchDto>(search);
    }
}
