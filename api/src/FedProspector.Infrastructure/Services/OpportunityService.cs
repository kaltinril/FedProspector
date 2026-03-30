using System.Text.Json;
using System.Text.RegularExpressions;
using FedProspector.Core.Constants;
using FedProspector.Core.DTOs;
using FedProspector.Core.DTOs.Opportunities;
using FedProspector.Core.Interfaces;
using FedProspector.Core.Options;
using FedProspector.Infrastructure.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace FedProspector.Infrastructure.Services;

public partial class OpportunityService : IOpportunityService
{
    private readonly FedProspectorDbContext _context;
    private readonly ILogger<OpportunityService> _logger;
    private readonly IHttpClientFactory _httpClientFactory;
    private readonly SamApiOptions _samApiOptions;

    public OpportunityService(
        FedProspectorDbContext context,
        ILogger<OpportunityService> logger,
        IHttpClientFactory httpClientFactory,
        IOptions<SamApiOptions> samApiOptions)
    {
        _context = context;
        _logger = logger;
        _httpClientFactory = httpClientFactory;
        _samApiOptions = samApiOptions.Value;
    }

    public async Task<PagedResponse<OpportunitySearchDto>> SearchAsync(OpportunitySearchRequest request, int organizationId)
    {
        var query = _context.Opportunities.AsNoTracking().AsQueryable();

        // Apply filters
        if (!string.IsNullOrWhiteSpace(request.SetAside))
            query = query.Where(o => o.SetAsideCode == request.SetAside);

        if (!string.IsNullOrWhiteSpace(request.Naics))
            query = query.Where(o => o.NaicsCode == request.Naics);

        if (!string.IsNullOrWhiteSpace(request.Solicitation))
        {
            var sol = EscapeLikePattern(request.Solicitation);
            query = query.Where(o => o.SolicitationNumber != null && EF.Functions.Like(o.SolicitationNumber, $"%{sol}%"));
        }

        if (!string.IsNullOrWhiteSpace(request.Keyword))
        {
            var kw = EscapeLikePattern(request.Keyword);
            query = query.Where(o =>
                (o.Title != null && EF.Functions.Like(o.Title, $"%{kw}%")) ||
                (o.SolicitationNumber != null && EF.Functions.Like(o.SolicitationNumber, $"%{kw}%")) ||
                (o.NoticeId != null && EF.Functions.Like(o.NoticeId, $"%{kw}%")));
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

        // Exclude non-biddable notice types
        query = query.Where(o => !OpportunityFilters.NonBiddableTypes.Contains(o.Type!));

        // Show only the latest notice per solicitation number (amendments supersede originals).
        // Opportunities without a solicitation number are always shown.
        query = query.Where(o =>
            (o.SolicitationNumber == null || o.SolicitationNumber == "") ||
            o.PostedDate == _context.Opportunities
                .Where(o2 => o2.SolicitationNumber == o.SolicitationNumber
                           && !OpportunityFilters.NonBiddableTypes.Contains(o2.Type!))
                .Max(o2 => o2.PostedDate));

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
            orderby o.PostedDate descending
            select new OpportunitySearchDto
            {
                NoticeId = o.NoticeId,
                Title = o.Title,
                SolicitationNumber = o.SolicitationNumber,
                DepartmentName = o.DepartmentName,
                Office = o.Office,
                ContractingOfficeId = o.ContractingOfficeId,
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
                "responsedeadline" => request.SortDescending ? enriched.OrderByDescending(x => x.ResponseDeadline) : enriched.OrderBy(x => x.ResponseDeadline),
                "departmentname" => request.SortDescending ? enriched.OrderByDescending(x => x.DepartmentName) : enriched.OrderBy(x => x.DepartmentName),
                "naicscode" => request.SortDescending ? enriched.OrderByDescending(x => x.NaicsCode) : enriched.OrderBy(x => x.NaicsCode),
                "baseandalloptions" => request.SortDescending ? enriched.OrderByDescending(x => x.BaseAndAllOptions) : enriched.OrderBy(x => x.BaseAndAllOptions),
                "popstate" => request.SortDescending ? enriched.OrderByDescending(x => x.PopState) : enriched.OrderBy(x => x.PopState),
                "solicitationnumber" => request.SortDescending ? enriched.OrderByDescending(x => x.SolicitationNumber) : enriched.OrderBy(x => x.SolicitationNumber),
                _ => request.SortDescending ? enriched.OrderByDescending(x => x.PostedDate) : enriched.OrderBy(x => x.PostedDate)
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
                .Take(50)
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
                Source = p.Source,
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
            // Search both PIID and solicitation_identifier with prefix match.
            // Perf note: could switch to exact match (==) if this ever needs to be faster.
            var ua = await _context.UsaspendingAwards.AsNoTracking()
                .FirstOrDefaultAsync(a => a.Piid!.StartsWith(opp.SolicitationNumber)
                    || (a.SolicitationIdentifier != null && a.SolicitationIdentifier.StartsWith(opp.SolicitationNumber)));
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

        // Points of contact
        var pocs = await _context.OpportunityPocs.AsNoTracking()
            .Where(p => p.NoticeId == noticeId)
            .Join(_context.ContractingOfficers.AsNoTracking(),
                p => p.OfficerId,
                o => o.OfficerId,
                (p, o) => new PointOfContactDto
                {
                    FullName = o.FullName,
                    Email = o.Email,
                    Phone = o.Phone,
                    Fax = o.Fax,
                    Title = o.Title,
                    PocType = p.PocType
                })
            .ToListAsync();

        // Amendment history: other notices with the same solicitation number
        var amendments = new List<AmendmentSummaryDto>();
        if (!string.IsNullOrWhiteSpace(opp.SolicitationNumber))
        {
            amendments = await _context.Opportunities.AsNoTracking()
                .Where(o => o.SolicitationNumber == opp.SolicitationNumber && o.NoticeId != noticeId)
                .OrderByDescending(o => o.PostedDate)
                .Select(o => new AmendmentSummaryDto
                {
                    NoticeId = o.NoticeId,
                    Title = o.Title,
                    Type = o.Type,
                    PostedDate = o.PostedDate,
                    ResponseDeadline = o.ResponseDeadline,
                    AwardeeName = o.AwardeeName,
                    AwardAmount = o.AwardAmount
                })
                .Take(50)
                .ToListAsync();
        }

        return new OpportunityDetailDto
        {
            NoticeId = opp.NoticeId,
            Title = opp.Title,
            SolicitationNumber = opp.SolicitationNumber,
            DepartmentName = opp.DepartmentName,
            SubTier = opp.SubTier,
            Office = opp.Office,
            ContractingOfficeId = opp.ContractingOfficeId,
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
            Link = NormalizeSamGovLink(opp.Link),
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
            PointsOfContact = pocs,
            Prospect = prospect,
            UsaspendingAward = usaAward,
            Amendments = amendments
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
                "solicitationnumber" => request.SortDescending ? query.OrderByDescending(t => t.SolicitationNumber) : query.OrderBy(t => t.SolicitationNumber),
                "departmentname" => request.SortDescending ? query.OrderByDescending(t => t.DepartmentName) : query.OrderBy(t => t.DepartmentName),
                "naicscode" => request.SortDescending ? query.OrderByDescending(t => t.NaicsCode) : query.OrderBy(t => t.NaicsCode),
                "responsedeadline" => request.SortDescending ? query.OrderByDescending(t => t.ResponseDeadline) : query.OrderBy(t => t.ResponseDeadline),
                "popstate" => request.SortDescending ? query.OrderByDescending(t => t.PopState) : query.OrderBy(t => t.PopState),
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
                ContractingOfficeId = t.ContractingOfficeId,
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

        // Transform workspace URLs to public SAM.gov URLs
        foreach (var item in items)
            item.Link = NormalizeSamGovLink(item.Link);

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

        if (!string.IsNullOrWhiteSpace(request.Solicitation))
        {
            var sol = EscapeLikePattern(request.Solicitation);
            query = query.Where(o => o.SolicitationNumber != null && EF.Functions.Like(o.SolicitationNumber, $"%{sol}%"));
        }

        if (!string.IsNullOrWhiteSpace(request.Keyword))
        {
            var kw = EscapeLikePattern(request.Keyword);
            query = query.Where(o =>
                (o.Title != null && EF.Functions.Like(o.Title, $"%{kw}%")) ||
                (o.SolicitationNumber != null && EF.Functions.Like(o.SolicitationNumber, $"%{kw}%")) ||
                (o.NoticeId != null && EF.Functions.Like(o.NoticeId, $"%{kw}%")));
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

        // Exclude non-biddable notice types
        query = query.Where(o => !OpportunityFilters.NonBiddableTypes.Contains(o.Type!));

        // Show only the latest notice per solicitation number (amendments supersede originals).
        // Opportunities without a solicitation number are always shown.
        query = query.Where(o =>
            (o.SolicitationNumber == null || o.SolicitationNumber == "") ||
            o.PostedDate == _context.Opportunities
                .Where(o2 => o2.SolicitationNumber == o.SolicitationNumber
                           && !OpportunityFilters.NonBiddableTypes.Contains(o2.Type!))
                .Max(o2 => o2.PostedDate));

        // Apply sort (same fields as SearchAsync)
        IOrderedQueryable<Core.Models.Opportunity> orderedQuery;
        if (!string.IsNullOrWhiteSpace(request.SortBy))
        {
            orderedQuery = request.SortBy.ToLowerInvariant() switch
            {
                "posteddate" => request.SortDescending ? query.OrderByDescending(o => o.PostedDate) : query.OrderBy(o => o.PostedDate),
                "title" => request.SortDescending ? query.OrderByDescending(o => o.Title) : query.OrderBy(o => o.Title),
                "solicitationnumber" => request.SortDescending ? query.OrderByDescending(o => o.SolicitationNumber) : query.OrderBy(o => o.SolicitationNumber),
                "departmentname" => request.SortDescending ? query.OrderByDescending(o => o.DepartmentName) : query.OrderBy(o => o.DepartmentName),
                "naicscode" => request.SortDescending ? query.OrderByDescending(o => o.NaicsCode) : query.OrderBy(o => o.NaicsCode),
                "responsedeadline" => request.SortDescending ? query.OrderByDescending(o => o.ResponseDeadline) : query.OrderBy(o => o.ResponseDeadline),
                "baseandalloptions" => request.SortDescending ? query.OrderByDescending(o => o.AwardAmount) : query.OrderBy(o => o.AwardAmount),
                "popstate" => request.SortDescending ? query.OrderByDescending(o => o.PopState) : query.OrderBy(o => o.PopState),
                _ => request.SortDescending ? query.OrderByDescending(o => o.ResponseDeadline) : query.OrderBy(o => o.ResponseDeadline)
            };
        }
        else
        {
            orderedQuery = query.OrderBy(o => o.ResponseDeadline);
        }

        // Limit to 5000 rows for CSV export
        var items = await orderedQuery
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

    public async Task<(string? descriptionText, string? error, bool notFound)> FetchDescriptionAsync(string noticeId)
    {
        var opp = await _context.Opportunities
            .FirstOrDefaultAsync(o => o.NoticeId == noticeId);

        if (opp == null)
            return (null, null, true);

        // Already have description text — return it without calling SAM.gov
        if (!string.IsNullOrWhiteSpace(opp.DescriptionText))
            return (opp.DescriptionText, null, false);

        if (string.IsNullOrWhiteSpace(opp.DescriptionUrl))
            return (null, "No description URL available for this opportunity.", true);

        // SSRF protection: only allow SAM.gov API URLs
        if (!opp.DescriptionUrl.StartsWith("https://api.sam.gov/", StringComparison.OrdinalIgnoreCase))
        {
            _logger.LogWarning("Blocked non-SAM.gov description URL for {NoticeId}: {Url}", noticeId, opp.DescriptionUrl);
            return (null, "Description URL is not a valid SAM.gov API URL.", false);
        }

        if (string.IsNullOrWhiteSpace(_samApiOptions.ApiKey))
        {
            _logger.LogError("SAM API key is not configured — cannot fetch description for {NoticeId}", noticeId);
            return (null, "SAM API key is not configured.", false);
        }

        try
        {
            // Append API key to the URL
            var separator = opp.DescriptionUrl.Contains('?') ? "&" : "?";
            var url = $"{opp.DescriptionUrl}{separator}api_key={_samApiOptions.ApiKey}";

            var client = _httpClientFactory.CreateClient("SamApi");
            var response = await client.GetAsync(url);

            if (!response.IsSuccessStatusCode)
            {
                _logger.LogWarning("SAM.gov noticedesc returned {StatusCode} for {NoticeId}",
                    (int)response.StatusCode, noticeId);
                return (null, $"SAM.gov returned HTTP {(int)response.StatusCode}.", false);
            }

            var json = await response.Content.ReadAsStringAsync();
            using var doc = JsonDocument.Parse(json);

            string? htmlDescription = null;
            if (doc.RootElement.TryGetProperty("description", out var descProp))
                htmlDescription = descProp.GetString();

            if (string.IsNullOrWhiteSpace(htmlDescription))
                return (null, "SAM.gov returned an empty description.", false);

            // Strip HTML tags
            var plainText = StripHtmlTags(htmlDescription);

            // Save to DB
            opp.DescriptionText = plainText;
            await _context.SaveChangesAsync();

            _logger.LogInformation("Fetched and saved description for {NoticeId} ({Length} chars)",
                noticeId, plainText.Length);

            return (plainText, null, false);
        }
        catch (HttpRequestException ex)
        {
            _logger.LogError(ex, "HTTP error fetching description for {NoticeId}", noticeId);
            return (null, $"Error contacting SAM.gov: {ex.Message}", false);
        }
        catch (JsonException ex)
        {
            _logger.LogError(ex, "JSON parse error for description response for {NoticeId}", noticeId);
            return (null, "Invalid JSON response from SAM.gov.", false);
        }
        catch (TaskCanceledException ex)
        {
            _logger.LogError(ex, "Timeout fetching description for {NoticeId}", noticeId);
            return (null, "Request to SAM.gov timed out.", false);
        }
    }

    [GeneratedRegex("<[^>]+>")]
    private static partial Regex HtmlTagRegex();

    private static string StripHtmlTags(string html)
    {
        // Decode common HTML entities, then strip tags
        var text = HtmlTagRegex().Replace(html, string.Empty);
        text = text.Replace("&nbsp;", " ")
                   .Replace("&amp;", "&")
                   .Replace("&lt;", "<")
                   .Replace("&gt;", ">")
                   .Replace("&quot;", "\"")
                   .Replace("&#39;", "'")
                   .Replace("&apos;", "'");
        // Collapse multiple whitespace/newlines into single spaces, then trim
        text = Regex.Replace(text, @"\s+", " ").Trim();
        return text;
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
    /// <summary>
    /// Transforms SAM.gov workspace URLs (which require login) to public URLs.
    /// e.g. /workspace/contract/opp/{id}/view -> /opp/{id}/view
    /// </summary>
    internal static string? NormalizeSamGovLink(string? link)
    {
        if (string.IsNullOrEmpty(link)) return link;
        return link.Replace("/workspace/contract/opp/", "/opp/");
    }

    private static string CsvField(object? value)
    {
        var s = value?.ToString() ?? "";
        // Neutralize CSV formula injection (Excel/LibreOffice interpret these as formulas)
        if (s.Length > 0 && "=+-@".Contains(s[0]))
            s = "'" + s;
        return $"\"{s.Replace("\"", "\"\"")}\"";
    }
}
