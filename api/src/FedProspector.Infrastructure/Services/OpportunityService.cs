using System.Text.Json;
using FedProspector.Core.DTOs;
using FedProspector.Core.DTOs.Opportunities;
using FedProspector.Core.Interfaces;
using FedProspector.Infrastructure.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;

namespace FedProspector.Infrastructure.Services;

public class OpportunityService : IOpportunityService
{
    private readonly FedProspectorDbContext _context;
    private readonly ILogger<OpportunityService> _logger;

    public OpportunityService(FedProspectorDbContext context, ILogger<OpportunityService> logger)
    {
        _context = context;
        _logger = logger;
    }

    public async Task<PagedResponse<OpportunitySearchDto>> SearchAsync(OpportunitySearchRequest request, int organizationId)
    {
        var query = _context.Opportunities.AsNoTracking().AsQueryable();

        // Apply filters
        if (!string.IsNullOrWhiteSpace(request.SetAside))
            query = query.Where(o => o.SetAsideCode == request.SetAside);

        if (!string.IsNullOrWhiteSpace(request.Naics))
            query = query.Where(o => o.NaicsCode == request.Naics);

        if (!string.IsNullOrWhiteSpace(request.Keyword))
        {
            var escapedKeyword = EscapeLikePattern(request.Keyword);
            query = query.Where(o => o.Title != null && EF.Functions.Like(o.Title, $"%{escapedKeyword}%"));
        }

        if (request.DaysOut.HasValue)
        {
            var deadline = DateTime.UtcNow.AddDays(request.DaysOut.Value);
            query = query.Where(o => o.ResponseDeadline != null && o.ResponseDeadline <= deadline);
        }

        if (request.OpenOnly)
            query = query.Where(o => o.Active == "Y" && o.ResponseDeadline != null && o.ResponseDeadline > DateTime.UtcNow);

        if (!string.IsNullOrWhiteSpace(request.Department))
        {
            var escapedDept = EscapeLikePattern(request.Department);
            query = query.Where(o => o.DepartmentName != null && EF.Functions.Like(o.DepartmentName, $"%{escapedDept}%"));
        }

        if (!string.IsNullOrWhiteSpace(request.State))
            query = query.Where(o => o.PopState == request.State);

        // Count before joining (more efficient)
        var totalCount = await query.CountAsync();

        // Join to reference tables + prospect for enrichment, then project
        var enriched = from o in query
            join n in _context.RefNaicsCodes on o.NaicsCode equals n.NaicsCode into naicsJoin
            from n in naicsJoin.DefaultIfEmpty()
            join sa in _context.RefSetAsideTypes on o.SetAsideCode equals sa.SetAsideCode into saJoin
            from sa in saJoin.DefaultIfEmpty()
            join p in _context.Prospects.Where(pr => pr.OrganizationId == organizationId) on o.NoticeId equals p.NoticeId into pJoin
            from p in pJoin.DefaultIfEmpty()
            join u in _context.AppUsers on p.AssignedTo equals u.UserId into uJoin
            from u in uJoin.DefaultIfEmpty()
            join sc in _context.RefStateCodes.Where(s => s.CountryCode == "USA") on o.PopState equals sc.StateCode into stateJoin
            from sc in stateJoin.DefaultIfEmpty()
            join cc in _context.RefCountryCodes on o.PopCountry equals cc.ThreeCode into countryJoin
            from cc in countryJoin.DefaultIfEmpty()
            orderby o.ResponseDeadline ascending
            select new OpportunitySearchDto
            {
                NoticeId = o.NoticeId,
                Title = o.Title,
                SolicitationNumber = o.SolicitationNumber,
                DepartmentName = o.DepartmentName,
                Office = o.Office,
                PostedDate = o.PostedDate,
                ResponseDeadline = o.ResponseDeadline,
                DaysUntilDue = o.ResponseDeadline != null
                    ? (int?)EF.Functions.DateDiffDay(DateTime.UtcNow, o.ResponseDeadline!.Value)
                    : null,
                SetAsideCode = o.SetAsideCode,
                SetAsideDescription = o.SetAsideDescription,
                SetAsideCategory = sa != null ? sa.Category : null,
                NaicsCode = o.NaicsCode,
                NaicsDescription = n != null ? n.Description : null,
                NaicsSector = null,
                SizeStandard = null,
                BaseAndAllOptions = o.AwardAmount,
                EstimatedContractValue = o.EstimatedContractValue,
                PopState = o.PopState,
                PopStateName = sc != null ? sc.StateName : o.PopState,
                PopCity = o.PopCity,
                PopCountry = o.PopCountry,
                PopCountryName = cc != null ? cc.CountryName : o.PopCountry,
                ProspectStatus = p != null ? p.Status : null,
                AssignedUser = u != null ? u.DisplayName : null
            };

        // Override sort if specified
        if (!string.IsNullOrWhiteSpace(request.SortBy))
        {
            enriched = request.SortBy.ToLowerInvariant() switch
            {
                "posteddate" => request.SortDescending ? enriched.OrderByDescending(x => x.PostedDate) : enriched.OrderBy(x => x.PostedDate),
                "title" => request.SortDescending ? enriched.OrderByDescending(x => x.Title) : enriched.OrderBy(x => x.Title),
                _ => enriched
            };
        }

        var items = await enriched
            .Skip((request.Page - 1) * request.PageSize)
            .Take(request.PageSize)
            .ToListAsync();

        return new PagedResponse<OpportunitySearchDto>
        {
            Items = items,
            Page = request.Page,
            PageSize = request.PageSize,
            TotalCount = totalCount
        };
    }

    public async Task<OpportunityDetailDto?> GetDetailAsync(string noticeId, int organizationId)
    {
        var opp = await _context.Opportunities.AsNoTracking()
            .FirstOrDefaultAsync(o => o.NoticeId == noticeId);

        if (opp == null) return null;

        // Look up NAICS reference data
        string? naicsDescription = null;
        string? naicsSector = null;
        string? sizeStandard = null;
        if (!string.IsNullOrWhiteSpace(opp.NaicsCode))
        {
            var naicsRef = await _context.RefNaicsCodes.AsNoTracking()
                .FirstOrDefaultAsync(n => n.NaicsCode == opp.NaicsCode);
            naicsDescription = naicsRef?.Description;

            var sbaRef = await _context.RefSbaSizeStandards.AsNoTracking()
                .FirstOrDefaultAsync(s => s.NaicsCode == opp.NaicsCode);
            sizeStandard = sbaRef?.SizeStandard?.ToString("N0");
        }

        // Look up set-aside category
        string? setAsideCategory = null;
        if (!string.IsNullOrWhiteSpace(opp.SetAsideCode))
        {
            var saRef = await _context.RefSetAsideTypes.AsNoTracking()
                .FirstOrDefaultAsync(sa => sa.SetAsideCode == opp.SetAsideCode);
            setAsideCategory = saRef?.Category;
        }

        // Look up state/country names
        string? popStateName = opp.PopState; // COALESCE: fallback to raw code
        if (!string.IsNullOrWhiteSpace(opp.PopState))
        {
            var stateRef = await _context.RefStateCodes.AsNoTracking()
                .FirstOrDefaultAsync(s => s.StateCode == opp.PopState && s.CountryCode == "USA");
            if (stateRef != null) popStateName = stateRef.StateName;
        }

        string? popCountryName = opp.PopCountry; // COALESCE: fallback to raw code
        if (!string.IsNullOrWhiteSpace(opp.PopCountry))
        {
            var countryRef = await _context.RefCountryCodes.AsNoTracking()
                .FirstOrDefaultAsync(c => c.ThreeCode == opp.PopCountry);
            if (countryRef != null) popCountryName = countryRef.CountryName;
        }

        // Related awards (base awards only, match on solicitation number)
        var relatedAwards = string.IsNullOrWhiteSpace(opp.SolicitationNumber)
            ? new List<RelatedAwardDto>()
            : await _context.FpdsContracts.AsNoTracking()
                .Where(c => c.SolicitationNumber == opp.SolicitationNumber && c.ModificationNumber == "0")
                .Select(c => new RelatedAwardDto
                {
                    ContractId = c.ContractId,
                    VendorName = c.VendorName,
                    VendorUei = c.VendorUei,
                    DateSigned = c.DateSigned,
                    DollarsObligated = c.DollarsObligated,
                    BaseAndAllOptions = c.BaseAndAllOptions,
                    TypeOfContract = c.TypeOfContract,
                    NumberOfOffers = c.NumberOfOffers
                })
                .ToListAsync();

        // Prospect info
        ProspectSummaryDto? prospect = null;
        var p = await _context.Prospects.AsNoTracking()
            .FirstOrDefaultAsync(pr => pr.NoticeId == noticeId && pr.OrganizationId == organizationId);
        if (p != null)
        {
            var assignee = p.AssignedTo.HasValue
                ? await _context.AppUsers.AsNoTracking()
                    .FirstOrDefaultAsync(u => u.UserId == p.AssignedTo.Value)
                : null;

            prospect = new ProspectSummaryDto
            {
                ProspectId = p.ProspectId,
                Status = p.Status,
                Priority = p.Priority,
                GoNoGoScore = p.GoNoGoScore,
                WinProbability = p.WinProbability,
                AssignedTo = assignee?.DisplayName
            };
        }

        // USASpending award
        UsaspendingSummaryDto? usaAward = null;
        if (!string.IsNullOrWhiteSpace(opp.SolicitationNumber))
        {
            var ua = await _context.UsaspendingAwards.AsNoTracking()
                .FirstOrDefaultAsync(a => a.SolicitationIdentifier == opp.SolicitationNumber);
            if (ua != null)
            {
                usaAward = new UsaspendingSummaryDto
                {
                    GeneratedUniqueAwardId = ua.GeneratedUniqueAwardId,
                    RecipientName = ua.RecipientName,
                    RecipientUei = ua.RecipientUei,
                    TotalObligation = ua.TotalObligation,
                    BaseAndAllOptionsValue = ua.BaseAndAllOptionsValue,
                    StartDate = ua.StartDate,
                    EndDate = ua.EndDate
                };
            }
        }

        return new OpportunityDetailDto
        {
            NoticeId = opp.NoticeId,
            Title = opp.Title,
            SolicitationNumber = opp.SolicitationNumber,
            DepartmentName = opp.DepartmentName,
            SubTier = opp.SubTier,
            Office = opp.Office,
            PostedDate = opp.PostedDate,
            ResponseDeadline = opp.ResponseDeadline,
            ArchiveDate = opp.ArchiveDate,
            Type = opp.Type,
            BaseType = opp.BaseType,
            SetAsideCode = opp.SetAsideCode,
            SetAsideDescription = opp.SetAsideDescription,
            ClassificationCode = opp.ClassificationCode,
            NaicsCode = opp.NaicsCode,
            NaicsDescription = naicsDescription,
            NaicsSector = naicsSector,
            SizeStandard = sizeStandard,
            SetAsideCategory = setAsideCategory,
            PopState = opp.PopState,
            PopStateName = popStateName,
            PopZip = opp.PopZip,
            PopCountry = opp.PopCountry,
            PopCountryName = popCountryName,
            PopCity = opp.PopCity,
            Active = opp.Active,
            AwardNumber = opp.AwardNumber,
            AwardDate = opp.AwardDate,
            AwardAmount = opp.AwardAmount,
            AwardeeUei = opp.AwardeeUei,
            AwardeeName = opp.AwardeeName,
            AwardeeCageCode = opp.AwardeeCageCode,
            AwardeeCity = opp.AwardeeCity,
            AwardeeState = opp.AwardeeState,
            AwardeeZip = opp.AwardeeZip,
            FullParentPathName = opp.FullParentPathName,
            FullParentPathCode = opp.FullParentPathCode,
            DescriptionUrl = opp.DescriptionUrl,
            DescriptionText = opp.DescriptionText,
            Link = opp.Link,
            ResourceLinks = opp.ResourceLinks,
            ResourceLinkDetails = ParseResourceLinks(opp.ResourceLinks),
            EstimatedContractValue = opp.EstimatedContractValue,
            SecurityClearanceRequired = opp.SecurityClearanceRequired,
            IncumbentUei = opp.IncumbentUei,
            IncumbentName = opp.IncumbentName,
            PeriodOfPerformanceStart = opp.PeriodOfPerformanceStart,
            PeriodOfPerformanceEnd = opp.PeriodOfPerformanceEnd,
            FirstLoadedAt = opp.FirstLoadedAt,
            LastLoadedAt = opp.LastLoadedAt,
            RelatedAwards = relatedAwards,
            Prospect = prospect,
            UsaspendingAward = usaAward
        };
    }

    public async Task<PagedResponse<TargetOpportunityDto>> GetTargetsAsync(TargetOpportunitySearchRequest request, int organizationId)
    {
        var query = _context.TargetOpportunities.AsNoTracking().AsQueryable();

        // Filter prospect data to current organization only
        query = query.Where(t => t.OrganizationId == null || t.OrganizationId == organizationId);

        // Apply optional filters on top of the view's built-in WOSB/8(a) filter
        if (request.MinValue.HasValue)
            query = query.Where(t => t.AwardAmount >= request.MinValue);

        if (request.MaxValue.HasValue)
            query = query.Where(t => t.AwardAmount <= request.MaxValue);

        if (!string.IsNullOrWhiteSpace(request.NaicsSector))
            query = query.Where(t => t.NaicsSector == request.NaicsSector);

        if (!string.IsNullOrWhiteSpace(request.SetAside))
            query = query.Where(t => t.SetAsideCode == request.SetAside);

        if (!string.IsNullOrWhiteSpace(request.Naics))
            query = query.Where(t => t.NaicsCode == request.Naics);

        if (!string.IsNullOrWhiteSpace(request.Department))
        {
            var escapedDept = EscapeLikePattern(request.Department);
            query = query.Where(t => t.DepartmentName != null && EF.Functions.Like(t.DepartmentName, $"%{escapedDept}%"));
        }

        if (!string.IsNullOrWhiteSpace(request.State))
            query = query.Where(t => t.PopState == request.State);

        var totalCount = await query.CountAsync();

        // Manual pagination (keyless entity — no PK for default ordering)
        var ordered = query.OrderBy(t => t.DaysUntilDue);

        if (!string.IsNullOrWhiteSpace(request.SortBy))
        {
            ordered = request.SortBy.ToLowerInvariant() switch
            {
                "posteddate" => request.SortDescending ? query.OrderByDescending(t => t.PostedDate) : query.OrderBy(t => t.PostedDate),
                "title" => request.SortDescending ? query.OrderByDescending(t => t.Title) : query.OrderBy(t => t.Title),
                "awardamount" => request.SortDescending ? query.OrderByDescending(t => t.AwardAmount) : query.OrderBy(t => t.AwardAmount),
                _ => ordered
            };
        }

        var items = await ordered
            .Skip((request.Page - 1) * request.PageSize)
            .Take(request.PageSize)
            .Select(t => new TargetOpportunityDto
            {
                NoticeId = t.NoticeId,
                Title = t.Title,
                SolicitationNumber = t.SolicitationNumber,
                DepartmentName = t.DepartmentName,
                Office = t.Office,
                PostedDate = t.PostedDate,
                ResponseDeadline = t.ResponseDeadline,
                DaysUntilDue = t.DaysUntilDue,
                SetAsideCode = t.SetAsideCode,
                SetAsideDescription = t.SetAsideDescription,
                SetAsideCategory = t.SetAsideCategory,
                NaicsCode = t.NaicsCode,
                NaicsDescription = t.NaicsDescription,
                NaicsLevel = t.NaicsLevel,
                NaicsSector = t.NaicsSector,
                SizeStandard = t.SizeStandard,
                SizeType = t.SizeType,
                AwardAmount = t.AwardAmount,
                PopState = t.PopState,
                PopCity = t.PopCity,
                DescriptionUrl = t.DescriptionUrl,
                Link = t.Link,
                ProspectId = t.ProspectId,
                ProspectStatus = t.ProspectStatus,
                ProspectPriority = t.ProspectPriority,
                AssignedTo = t.AssignedTo
            })
            .ToListAsync();

        return new PagedResponse<TargetOpportunityDto>
        {
            Items = items,
            Page = request.Page,
            PageSize = request.PageSize,
            TotalCount = totalCount
        };
    }

    public async Task<string> ExportCsvAsync(OpportunitySearchRequest request, int organizationId)
    {
        // Build the same query as SearchAsync but without pagination
        // organizationId available for future prospect-enriched CSV exports (same pattern as SearchAsync)
        var query = _context.Opportunities.AsNoTracking().AsQueryable();

        if (!string.IsNullOrWhiteSpace(request.SetAside))
            query = query.Where(o => o.SetAsideCode == request.SetAside);

        if (!string.IsNullOrWhiteSpace(request.Naics))
            query = query.Where(o => o.NaicsCode == request.Naics);

        if (!string.IsNullOrWhiteSpace(request.Keyword))
        {
            var escapedKeyword = EscapeLikePattern(request.Keyword);
            query = query.Where(o => o.Title != null && EF.Functions.Like(o.Title, $"%{escapedKeyword}%"));
        }

        if (request.DaysOut.HasValue)
        {
            var deadline = DateTime.UtcNow.AddDays(request.DaysOut.Value);
            query = query.Where(o => o.ResponseDeadline != null && o.ResponseDeadline <= deadline);
        }

        if (request.OpenOnly)
            query = query.Where(o => o.Active == "Y" && o.ResponseDeadline != null && o.ResponseDeadline > DateTime.UtcNow);

        if (!string.IsNullOrWhiteSpace(request.Department))
        {
            var escapedDept = EscapeLikePattern(request.Department);
            query = query.Where(o => o.DepartmentName != null && EF.Functions.Like(o.DepartmentName, $"%{escapedDept}%"));
        }

        if (!string.IsNullOrWhiteSpace(request.State))
            query = query.Where(o => o.PopState == request.State);

        // Limit to 5000 rows for CSV export
        var items = await query
            .OrderBy(o => o.ResponseDeadline)
            .Take(5000)
            .Select(o => new
            {
                o.NoticeId,
                o.Title,
                o.SolicitationNumber,
                o.DepartmentName,
                o.Office,
                o.PostedDate,
                o.ResponseDeadline,
                o.SetAsideCode,
                o.NaicsCode,
                o.PopState,
                o.AwardAmount,
                o.Active
            })
            .ToListAsync();

        var sb = new System.Text.StringBuilder();
        sb.AppendLine("NoticeId,Title,SolicitationNumber,Department,Office,PostedDate,ResponseDeadline,SetAsideCode,NaicsCode,State,AwardAmount,Active");

        foreach (var item in items)
        {
            sb.AppendLine($"{CsvField(item.NoticeId)},{CsvField(item.Title)},{CsvField(item.SolicitationNumber)},{CsvField(item.DepartmentName)},{CsvField(item.Office)},{CsvField(item.PostedDate)},{CsvField(item.ResponseDeadline)},{CsvField(item.SetAsideCode)},{CsvField(item.NaicsCode)},{CsvField(item.PopState)},{CsvField(item.AwardAmount)},{CsvField(item.Active)}");
        }

        return sb.ToString();
    }

    /// <summary>
    /// Parses the resource_links JSON column into structured DTOs.
    /// Handles both old format (array of URL strings) and new format (array of objects with url/filename/content_type).
    /// </summary>
    private static List<ResourceLinkDto> ParseResourceLinks(string? json)
    {
        if (string.IsNullOrWhiteSpace(json)) return [];

        try
        {
            using var doc = JsonDocument.Parse(json);
            var result = new List<ResourceLinkDto>();

            foreach (var element in doc.RootElement.EnumerateArray())
            {
                if (element.ValueKind == JsonValueKind.String)
                {
                    // Old format: plain URL string
                    result.Add(new ResourceLinkDto { Url = element.GetString() ?? string.Empty });
                }
                else if (element.ValueKind == JsonValueKind.Object)
                {
                    // New format: object with url, filename, content_type
                    result.Add(new ResourceLinkDto
                    {
                        Url = element.TryGetProperty("url", out var urlProp) ? urlProp.GetString() ?? string.Empty : string.Empty,
                        Filename = element.TryGetProperty("filename", out var fProp) ? fProp.GetString() : null,
                        ContentType = element.TryGetProperty("content_type", out var ctProp) ? ctProp.GetString() : null
                    });
                }
            }

            return result;
        }
        catch (JsonException)
        {
            return [];
        }
    }

    /// <summary>
    /// Escapes LIKE special characters (%, _, \) so user input is treated as literals.
    /// </summary>
    private static string EscapeLikePattern(string input)
    {
        if (string.IsNullOrEmpty(input)) return input;
        return input.Replace("\\", "\\\\").Replace("%", "\\%").Replace("_", "\\_");
    }

    /// <summary>
    /// Formats a value for CSV output. Quotes all fields and neutralizes formula injection
    /// by prefixing values that start with =, +, -, or @ with a single quote.
    /// </summary>
    private static string CsvField(object? value)
    {
        var s = value?.ToString() ?? "";
        // Neutralize CSV formula injection (Excel/LibreOffice interpret these as formulas)
        if (s.Length > 0 && "=+-@".Contains(s[0]))
            s = "'" + s;
        return $"\"{s.Replace("\"", "\"\"")}\"";
    }
}
