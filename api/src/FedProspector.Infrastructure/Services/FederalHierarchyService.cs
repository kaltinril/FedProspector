using FedProspector.Core.DTOs;
using FedProspector.Core.DTOs.FederalHierarchy;
using FedProspector.Core.DTOs.Opportunities;
using FedProspector.Core.Interfaces;
using FedProspector.Core.Models;
using FedProspector.Infrastructure.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;

namespace FedProspector.Infrastructure.Services;

public class FederalHierarchyService : IFederalHierarchyService
{
    private readonly FedProspectorDbContext _context;
    private readonly ILogger<FederalHierarchyService> _logger;

    public FederalHierarchyService(
        FedProspectorDbContext context,
        ILogger<FederalHierarchyService> logger)
    {
        _context = context;
        _logger = logger;
    }

    public async Task<PagedResponse<FederalOrgListItemDto>> SearchAsync(FederalOrgSearchRequestDto request)
    {
        var query = _context.FederalOrganizations.AsNoTracking().AsQueryable();

        if (!string.IsNullOrWhiteSpace(request.Keyword))
        {
            var kw = EscapeLikePattern(request.Keyword);
            query = query.Where(o =>
                (o.FhOrgName != null && EF.Functions.Like(o.FhOrgName, $"%{kw}%")) ||
                (o.AgencyCode != null && EF.Functions.Like(o.AgencyCode, $"%{kw}%")) ||
                (o.Cgac != null && EF.Functions.Like(o.Cgac, $"%{kw}%")));
        }

        if (!string.IsNullOrWhiteSpace(request.FhOrgType))
            query = query.Where(o => o.FhOrgType == request.FhOrgType);

        if (!string.IsNullOrWhiteSpace(request.Status))
            query = query.Where(o => o.Status == request.Status);

        if (!string.IsNullOrWhiteSpace(request.AgencyCode))
            query = query.Where(o => o.AgencyCode == request.AgencyCode);

        if (!string.IsNullOrWhiteSpace(request.Cgac))
            query = query.Where(o => o.Cgac == request.Cgac);

        if (request.Level.HasValue)
            query = query.Where(o => o.Level == request.Level.Value);

        if (request.ParentOrgId.HasValue)
            query = query.Where(o => o.ParentOrgId == request.ParentOrgId.Value);

        var totalCount = await query.CountAsync();

        // Sorting
        query = request.SortBy?.ToLowerInvariant() switch
        {
            "name" => request.SortDescending ? query.OrderByDescending(o => o.FhOrgName) : query.OrderBy(o => o.FhOrgName),
            "type" => request.SortDescending ? query.OrderByDescending(o => o.FhOrgType) : query.OrderBy(o => o.FhOrgType),
            "level" => request.SortDescending ? query.OrderByDescending(o => o.Level) : query.OrderBy(o => o.Level),
            "status" => request.SortDescending ? query.OrderByDescending(o => o.Status) : query.OrderBy(o => o.Status),
            _ => query.OrderBy(o => o.FhOrgName)
        };

        var items = await query
            .Skip((request.Page - 1) * request.PageSize)
            .Take(request.PageSize)
            .Select(o => new FederalOrgListItemDto
            {
                FhOrgId = o.FhOrgId,
                FhOrgName = o.FhOrgName,
                FhOrgType = o.FhOrgType,
                Status = o.Status,
                AgencyCode = o.AgencyCode,
                Cgac = o.Cgac,
                Level = o.Level,
                ParentOrgId = o.ParentOrgId
            })
            .ToListAsync();

        return new PagedResponse<FederalOrgListItemDto>
        {
            Items = items,
            Page = request.Page,
            PageSize = request.PageSize,
            TotalCount = totalCount
        };
    }

    public async Task<FederalOrgDetailDto?> GetDetailAsync(int fhOrgId)
    {
        var org = await _context.FederalOrganizations.AsNoTracking()
            .FirstOrDefaultAsync(o => o.FhOrgId == fhOrgId);

        if (org == null) return null;

        var detail = new FederalOrgDetailDto
        {
            FhOrgId = org.FhOrgId,
            FhOrgName = org.FhOrgName,
            FhOrgType = org.FhOrgType,
            Status = org.Status,
            AgencyCode = org.AgencyCode,
            Cgac = org.Cgac,
            Level = org.Level,
            ParentOrgId = org.ParentOrgId,
            Description = org.Description,
            OldfpdsOfficeCode = org.OldfpdsOfficeCode,
            CreatedDate = org.CreatedDate,
            LastModifiedDate = org.LastModifiedDate,
            LastLoadedAt = org.LastLoadedAt,
            ChildCount = await _context.FederalOrganizations.AsNoTracking()
                .CountAsync(c => c.ParentOrgId == org.FhOrgId),
            ParentChain = await BuildParentChainAsync(org.ParentOrgId)
        };

        return detail;
    }

    public async Task<List<FederalOrgListItemDto>> GetChildrenAsync(int fhOrgId, string? status = null, string? keyword = null)
    {
        var query = _context.FederalOrganizations.AsNoTracking()
            .Where(o => o.ParentOrgId == fhOrgId);

        if (!string.IsNullOrWhiteSpace(status) && !status.Equals("All", StringComparison.OrdinalIgnoreCase))
            query = query.Where(o => o.Status == status);

        if (!string.IsNullOrWhiteSpace(keyword))
        {
            var kw = EscapeLikePattern(keyword);

            // Find children of this parent that have matching descendants (or match themselves).
            // Step 1: Get IDs of grandchildren that match
            var matchingGrandchildParentIds = await _context.FederalOrganizations.AsNoTracking()
                .Where(gc => gc.FhOrgName != null && EF.Functions.Like(gc.FhOrgName, $"%{kw}%"))
                .Where(gc => gc.ParentOrgId != null)
                .Join(_context.FederalOrganizations.AsNoTracking().Where(c => c.ParentOrgId == fhOrgId),
                    gc => gc.ParentOrgId, c => c.FhOrgId, (gc, c) => c.FhOrgId)
                .Distinct()
                .ToListAsync();
            var ancestorIds = new HashSet<int>(matchingGrandchildParentIds);

            // Step 2: Include children that match directly
            query = query.Where(c =>
                (c.FhOrgName != null && EF.Functions.Like(c.FhOrgName, $"%{kw}%"))
                || ancestorIds.Contains(c.FhOrgId));
        }

        var children = await query
            .OrderBy(o => o.FhOrgName)
            .Select(o => new FederalOrgListItemDto
            {
                FhOrgId = o.FhOrgId,
                FhOrgName = o.FhOrgName,
                FhOrgType = o.FhOrgType,
                Status = o.Status,
                AgencyCode = o.AgencyCode,
                Cgac = o.Cgac,
                Level = o.Level,
                ParentOrgId = o.ParentOrgId
            })
            .ToListAsync();

        // Populate child counts so the tree knows which nodes are expandable
        if (children.Count > 0)
        {
            var childIds = children.Select(c => c.FhOrgId).ToList();
            var counts = await _context.FederalOrganizations.AsNoTracking()
                .Where(o => o.ParentOrgId != null && childIds.Contains(o.ParentOrgId.Value))
                .GroupBy(o => o.ParentOrgId!.Value)
                .Select(g => new { ParentId = g.Key, Count = g.Count() })
                .ToListAsync();
            var countDict = counts.ToDictionary(c => c.ParentId, c => c.Count);

            foreach (var child in children)
                child.ChildCount = countDict.GetValueOrDefault(child.FhOrgId, 0);
        }

        return children;
    }

    public async Task<List<FederalOrgTreeNodeDto>> GetTreeAsync(string? keyword = null)
    {
        if (!string.IsNullOrWhiteSpace(keyword))
        {
            // Fast path: find matching orgs first, then collect their ancestor department IDs.
            // This avoids nested EXISTS across 150K+ rows.
            var kw = EscapeLikePattern(keyword);

            // Step 1: Find all orgs matching the keyword
            var matchingOrgs = await _context.FederalOrganizations.AsNoTracking()
                .Where(o => o.FhOrgName != null && EF.Functions.Like(o.FhOrgName, $"%{kw}%"))
                .Select(o => new { o.FhOrgId, o.Level, o.ParentOrgId })
                .ToListAsync();

            // Step 2: Collect department IDs — walk up from matches to level 1
            var deptIds = new HashSet<int>();
            var level2Ids = new HashSet<int>();

            foreach (var m in matchingOrgs)
            {
                if (m.Level == 1)
                    deptIds.Add(m.FhOrgId);
                else if (m.Level == 2 && m.ParentOrgId.HasValue)
                {
                    deptIds.Add(m.ParentOrgId.Value);
                    level2Ids.Add(m.FhOrgId);
                }
                else if ((m.Level == 3 || m.Level == null) && m.ParentOrgId.HasValue)
                    level2Ids.Add(m.ParentOrgId.Value); // resolve to dept below
            }

            // Resolve level-2 IDs to their parent department IDs
            if (level2Ids.Count > 0)
            {
                var level2Parents = await _context.FederalOrganizations.AsNoTracking()
                    .Where(o => level2Ids.Contains(o.FhOrgId) && o.ParentOrgId != null)
                    .Select(o => o.ParentOrgId!.Value)
                    .Distinct()
                    .ToListAsync();
                foreach (var id in level2Parents)
                    deptIds.Add(id);
            }

            // Step 3: Get those departments
            var departments = await _context.FederalOrganizations.AsNoTracking()
                .Where(o => deptIds.Contains(o.FhOrgId) && o.Status == "Active")
                .OrderBy(o => o.FhOrgName)
                .Select(o => new { o.FhOrgId, o.FhOrgName })
                .ToListAsync();

            // Step 4: Child counts for filtered departments
            var filteredDeptIds = departments.Select(d => d.FhOrgId).ToList();
            var childCounts = await _context.FederalOrganizations.AsNoTracking()
                .Where(o => o.ParentOrgId != null && filteredDeptIds.Contains(o.ParentOrgId.Value))
                .GroupBy(o => o.ParentOrgId)
                .Select(g => new { ParentOrgId = g.Key, Count = g.Count() })
                .ToListAsync();
            var childCountDict = childCounts.ToDictionary(c => c.ParentOrgId!.Value, c => c.Count);

            return departments.Select(d => new FederalOrgTreeNodeDto
            {
                FhOrgId = d.FhOrgId,
                FhOrgName = d.FhOrgName,
                ChildCount = childCountDict.GetValueOrDefault(d.FhOrgId),
                DescendantCount = childCountDict.GetValueOrDefault(d.FhOrgId)
            }).ToList();
        }

        // No keyword — return all active departments with full counts
        var query = _context.FederalOrganizations.AsNoTracking()
            .Where(o => o.Level == 1 && o.Status == "Active");

        var allDepartments = await query
            .OrderBy(o => o.FhOrgName)
            .Select(o => new { o.FhOrgId, o.FhOrgName })
            .ToListAsync();

        var allDeptIds = allDepartments.Select(d => d.FhOrgId).ToList();

        // Get child counts (direct children) per department
        var allChildCounts = await _context.FederalOrganizations.AsNoTracking()
            .Where(o => o.ParentOrgId != null && allDeptIds.Contains(o.ParentOrgId.Value))
            .GroupBy(o => o.ParentOrgId)
            .Select(g => new { ParentOrgId = g.Key, Count = g.Count() })
            .ToListAsync();
        var allChildCountDict = allChildCounts.ToDictionary(c => c.ParentOrgId!.Value, c => c.Count);

        // Get descendant counts (sub-tiers + offices) per department
        var subTierIds = await _context.FederalOrganizations.AsNoTracking()
            .Where(o => o.ParentOrgId != null && allDeptIds.Contains(o.ParentOrgId.Value))
            .Select(o => new { o.FhOrgId, o.ParentOrgId })
            .ToListAsync();

        var subTierIdSet = subTierIds.Select(s => s.FhOrgId).ToHashSet();
        var subTierByDept = subTierIds.GroupBy(s => s.ParentOrgId!.Value)
            .ToDictionary(g => g.Key, g => g.Select(s => s.FhOrgId).ToList());

        var officeCounts = await _context.FederalOrganizations.AsNoTracking()
            .Where(o => o.ParentOrgId != null && subTierIdSet.Contains(o.ParentOrgId.Value))
            .GroupBy(o => o.ParentOrgId)
            .Select(g => new { ParentOrgId = g.Key, Count = g.Count() })
            .ToListAsync();
        var officeCountDict = officeCounts.ToDictionary(c => c.ParentOrgId!.Value, c => c.Count);

        return allDepartments.Select(d =>
        {
            var directChildren = allChildCountDict.GetValueOrDefault(d.FhOrgId);
            var officeDescendants = 0;
            if (subTierByDept.TryGetValue(d.FhOrgId, out var stIds))
                officeDescendants = stIds.Sum(stId => officeCountDict.GetValueOrDefault(stId));

            return new FederalOrgTreeNodeDto
            {
                FhOrgId = d.FhOrgId,
                FhOrgName = d.FhOrgName,
                ChildCount = directChildren,
                DescendantCount = directChildren + officeDescendants
            };
        }).ToList();
    }

    public async Task<PagedResponse<OpportunitySearchDto>> GetOpportunitiesAsync(int fhOrgId, PagedRequest request, string? active = null, string? type = null, string? setAsideCode = null)
    {
        // Get the org and its descendants' names and CGAC codes for matching
        var (orgNames, orgCgacs) = await GetOrgAndDescendantNamesAndCgacsAsync(fhOrgId);
        if (orgNames.Count == 0 && orgCgacs.Count == 0)
            return EmptyPaged<OpportunitySearchDto>(request);

        var query = _context.Opportunities.AsNoTracking()
            .Where(o =>
                (orgCgacs.Count > 0 && o.DepartmentCgac != null && orgCgacs.Contains(o.DepartmentCgac)) ||
                (o.DepartmentName != null && orgNames.Contains(o.DepartmentName)) ||
                (o.SubTier != null && orgNames.Contains(o.SubTier)) ||
                (o.Office != null && orgNames.Contains(o.Office)));

        if (!string.IsNullOrWhiteSpace(active))
            query = query.Where(o => o.Active == active);

        if (!string.IsNullOrWhiteSpace(type))
            query = query.Where(o => o.Type == type);

        if (!string.IsNullOrWhiteSpace(setAsideCode))
            query = query.Where(o => o.SetAsideCode == setAsideCode);

        var totalCount = await query.CountAsync();

        var items = await query
            .OrderByDescending(o => o.PostedDate)
            .Skip((request.Page - 1) * request.PageSize)
            .Take(request.PageSize)
            .Select(o => new OpportunitySearchDto
            {
                NoticeId = o.NoticeId,
                Title = o.Title,
                SolicitationNumber = o.SolicitationNumber,
                DepartmentName = o.DepartmentName,
                Office = o.Office,
                ContractingOfficeId = o.ContractingOfficeId,
                PostedDate = o.PostedDate,
                ResponseDeadline = o.ResponseDeadline,
                SetAsideCode = o.SetAsideCode,
                SetAsideDescription = o.SetAsideDescription,
                NaicsCode = o.NaicsCode,
                EstimatedContractValue = o.EstimatedContractValue,
                PopState = o.PopState
            })
            .ToListAsync();

        return new PagedResponse<OpportunitySearchDto>
        {
            Items = items,
            Page = request.Page,
            PageSize = request.PageSize,
            TotalCount = totalCount
        };
    }

    public async Task<HierarchyRefreshStatusDto> GetRefreshStatusAsync()
    {
        // Check etl_load_log for latest fedhier loads
        var latestLoad = await _context.EtlLoadLogs.AsNoTracking()
            .Where(l => l.SourceSystem == "fedhier")
            .OrderByDescending(l => l.StartedAt)
            .FirstOrDefaultAsync();

        var isRunning = latestLoad != null && latestLoad.Status == "running";

        // Get counts per level from the federal_organization table
        var levelCounts = await _context.FederalOrganizations.AsNoTracking()
            .Where(o => o.Level != null)
            .GroupBy(o => o.Level!.Value)
            .Select(g => new HierarchyLevelCount { Level = g.Key, Count = g.Count() })
            .OrderBy(l => l.Level)
            .ToListAsync();

        return new HierarchyRefreshStatusDto
        {
            IsRunning = isRunning,
            LastRefreshAt = latestLoad?.CompletedAt ?? latestLoad?.StartedAt,
            LastRefreshRecordCount = latestLoad != null
                ? latestLoad.RecordsInserted + latestLoad.RecordsUpdated + latestLoad.RecordsUnchanged
                : null,
            LevelsLoaded = levelCounts,
            JobId = latestLoad?.LoadId
        };
    }

    public async Task<int> RequestRefreshAsync(string fhOrgId, int userId)
    {
        // Check for existing pending/processing request (duplicate detection)
        var existing = await _context.DataLoadRequests
            .Where(r => r.RequestType == "REFRESH_FEDHIER_ORG"
                     && r.LookupKey == fhOrgId
                     && (r.Status == "PENDING" || r.Status == "PROCESSING"))
            .FirstOrDefaultAsync();

        if (existing != null)
            return existing.RequestId;

        var request = new DataLoadRequest
        {
            RequestType = "REFRESH_FEDHIER_ORG",
            LookupKey = fhOrgId,
            LookupKeyType = "FH_ORG_ID",
            Status = "PENDING",
            RequestedBy = userId,
            RequestedAt = DateTime.UtcNow
        };

        _context.DataLoadRequests.Add(request);
        await _context.SaveChangesAsync();

        _logger.LogInformation(
            "Queued refresh request {RequestId} for federal organization fhOrgId={FhOrgId}",
            request.RequestId, fhOrgId);

        return request.RequestId;
    }

    // --- Private helpers ---

    private async Task<List<FederalOrgBreadcrumbDto>> BuildParentChainAsync(int? parentOrgId)
    {
        var chain = new List<FederalOrgBreadcrumbDto>();
        var currentParentId = parentOrgId;
        var visited = new HashSet<int>(); // guard against cycles

        while (currentParentId.HasValue && visited.Add(currentParentId.Value))
        {
            var parent = await _context.FederalOrganizations.AsNoTracking()
                .Where(o => o.FhOrgId == currentParentId.Value)
                .Select(o => new FederalOrgBreadcrumbDto
                {
                    FhOrgId = o.FhOrgId,
                    FhOrgName = o.FhOrgName,
                    FhOrgType = o.FhOrgType,
                    Level = o.Level
                })
                .FirstOrDefaultAsync();

            if (parent == null) break;

            chain.Add(parent);
            currentParentId = await _context.FederalOrganizations.AsNoTracking()
                .Where(o => o.FhOrgId == parent.FhOrgId)
                .Select(o => o.ParentOrgId)
                .FirstOrDefaultAsync();
        }

        // Reverse so chain goes from root (department) down to immediate parent
        chain.Reverse();
        return chain;
    }

    /// <summary>
    /// Gets the org name/CGAC and all descendant org names/CGACs for use in matching.
    /// Returns both name set (for text fallback) and CGAC set (for code-based matching).
    /// </summary>
    private async Task<(HashSet<string> Names, HashSet<string> Cgacs)> GetOrgAndDescendantNamesAndCgacsAsync(int fhOrgId)
    {
        var org = await _context.FederalOrganizations.AsNoTracking()
            .FirstOrDefaultAsync(o => o.FhOrgId == fhOrgId);

        if (org == null) return ([], []);

        var names = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var cgacs = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        if (!string.IsNullOrWhiteSpace(org.FhOrgName))
            names.Add(org.FhOrgName);
        if (!string.IsNullOrWhiteSpace(org.Cgac))
            cgacs.Add(org.Cgac);

        // Get direct children
        var children = await _context.FederalOrganizations.AsNoTracking()
            .Where(o => o.ParentOrgId == fhOrgId)
            .Select(o => new { o.FhOrgId, o.FhOrgName, o.Cgac })
            .ToListAsync();

        foreach (var child in children)
        {
            if (!string.IsNullOrWhiteSpace(child.FhOrgName))
                names.Add(child.FhOrgName);
            if (!string.IsNullOrWhiteSpace(child.Cgac))
                cgacs.Add(child.Cgac);
        }

        // Get grandchildren (level 3) if the org is a department (level 1)
        if (org.Level == 1 && children.Count > 0)
        {
            var childIds = children.Select(c => c.FhOrgId).ToList();
            var grandchildren = await _context.FederalOrganizations.AsNoTracking()
                .Where(o => o.ParentOrgId != null && childIds.Contains(o.ParentOrgId.Value))
                .Select(o => new { o.FhOrgName, o.Cgac })
                .ToListAsync();

            foreach (var gc in grandchildren)
            {
                if (!string.IsNullOrWhiteSpace(gc.FhOrgName))
                    names.Add(gc.FhOrgName);
                if (!string.IsNullOrWhiteSpace(gc.Cgac))
                    cgacs.Add(gc.Cgac);
            }
        }

        return (names, cgacs);
    }

    private static PagedResponse<T> EmptyPaged<T>(PagedRequest request) => new()
    {
        Items = [],
        Page = request.Page,
        PageSize = request.PageSize,
        TotalCount = 0
    };

    /// <summary>
    /// Escapes LIKE special characters (%, _, \) so user input is treated as literals.
    /// </summary>
    private static string EscapeLikePattern(string input)
    {
        if (string.IsNullOrEmpty(input)) return input;
        return input.Replace("\\", "\\\\").Replace("%", "\\%").Replace("_", "\\_");
    }

}
