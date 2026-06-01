using FedProspector.Core.DTOs.Opportunities;
using FedProspector.Core.DTOs.Organizations;
using FedProspector.Core.Interfaces;
using FedProspector.Core.Models;
using FedProspector.Core.Options;
using FedProspector.Infrastructure.Data;
using FedProspector.Infrastructure.Services;
using FluentAssertions;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging.Abstractions;
using Microsoft.Extensions.Options;
using Moq;

namespace FedProspector.Infrastructure.Tests.Services;

public class OpportunityServiceTests : IDisposable
{
    private readonly FedProspectorDbContext _context;
    private readonly OpportunityService _service;

    public OpportunityServiceTests()
    {
        var options = new DbContextOptionsBuilder<FedProspectorDbContext>()
            .UseInMemoryDatabase(databaseName: Guid.NewGuid().ToString())
            .Options;

        _context = new FedProspectorDbContext(options);
        var httpClientFactory = Mock.Of<IHttpClientFactory>();
        var samApiOptions = Options.Create(new SamApiOptions());
        _service = new OpportunityService(_context, NullLogger<OpportunityService>.Instance, httpClientFactory, samApiOptions, CreateCompanyProfileServiceMock());
    }

    public void Dispose()
    {
        _context.Dispose();
    }

    // -----------------------------------------------------------------------
    // Seed Helpers
    // -----------------------------------------------------------------------

    private void SeedOpportunity(
        string noticeId,
        string? title = null,
        string? naicsCode = null,
        string? setAsideCode = null,
        DateTime? responseDeadline = null,
        string? active = "Y",
        string? departmentName = null,
        string? popState = null)
    {
        _context.Opportunities.Add(new Opportunity
        {
            NoticeId = noticeId,
            Title = title ?? $"Opportunity {noticeId}",
            NaicsCode = naicsCode,
            SetAsideCode = setAsideCode,
            ResponseDeadline = responseDeadline,
            Active = active,
            DepartmentName = departmentName,
            PopState = popState
        });
        _context.SaveChanges();
    }

    private void SeedMultipleOpportunities(int count, string? naicsCode = null, string? setAsideCode = null)
    {
        for (int i = 1; i <= count; i++)
        {
            SeedOpportunity(
                $"NOTICE-{i:D3}",
                naicsCode: naicsCode,
                setAsideCode: setAsideCode,
                responseDeadline: DateTime.UtcNow.AddDays(30 + i));
        }
    }

    // -----------------------------------------------------------------------
    // SearchAsync Tests
    //
    // SearchAsync uses EF.Functions.DateDiffDay in its Select projection
    // to compute DaysUntilDue. This MySQL-specific function is not supported
    // by the InMemory provider, so SearchAsync tests are skipped here.
    // These should be covered by integration tests against a real MySQL DB.
    // -----------------------------------------------------------------------

    [Fact(Skip = "EF.Functions.DateDiffDay in Select projection is not supported by InMemory provider")]
    public async Task SearchAsync_ReturnsPagedResults()
    {
        SeedMultipleOpportunities(5);

        var request = new OpportunitySearchRequest
        {
            Page = 1,
            PageSize = 3,
            OpenOnly = false
        };

        var result = await _service.SearchAsync(request, organizationId: 1);

        result.TotalCount.Should().Be(5);
        result.Items.Count().Should().Be(3);
        result.Page.Should().Be(1);
        result.PageSize.Should().Be(3);
        result.HasNextPage.Should().BeTrue();
    }

    [Fact(Skip = "EF.Functions.DateDiffDay in Select projection is not supported by InMemory provider")]
    public async Task SearchAsync_FiltersByNaics()
    {
        SeedOpportunity("NOTICE-IT", naicsCode: "541512");
        SeedOpportunity("NOTICE-CONSTRUCTION", naicsCode: "236220");

        var request = new OpportunitySearchRequest
        {
            Naics = "541512",
            OpenOnly = false
        };

        var result = await _service.SearchAsync(request, organizationId: 1);

        result.TotalCount.Should().Be(1);
        result.Items.Should().ContainSingle(o => o.NoticeId == "NOTICE-IT");
    }

    [Fact(Skip = "EF.Functions.DateDiffDay in Select projection is not supported by InMemory provider")]
    public async Task SearchAsync_FiltersBySetAside()
    {
        SeedOpportunity("NOTICE-WOSB", setAsideCode: "WOSB");
        SeedOpportunity("NOTICE-8A", setAsideCode: "8A");
        SeedOpportunity("NOTICE-NONE", setAsideCode: null);

        var request = new OpportunitySearchRequest
        {
            SetAside = "WOSB",
            OpenOnly = false
        };

        var result = await _service.SearchAsync(request, organizationId: 1);

        result.TotalCount.Should().Be(1);
        result.Items.Should().ContainSingle(o => o.NoticeId == "NOTICE-WOSB");
    }

    [Fact(Skip = "EF.Functions.DateDiffDay in Select projection is not supported by InMemory provider")]
    public async Task SearchAsync_FiltersByDateRange()
    {
        // Opportunity with deadline in 10 days
        SeedOpportunity("NOTICE-SOON", responseDeadline: DateTime.UtcNow.AddDays(10));
        // Opportunity with deadline in 90 days
        SeedOpportunity("NOTICE-LATER", responseDeadline: DateTime.UtcNow.AddDays(90));

        var request = new OpportunitySearchRequest
        {
            DaysOut = 30,
            OpenOnly = false
        };

        var result = await _service.SearchAsync(request, organizationId: 1);

        result.TotalCount.Should().Be(1);
        result.Items.Should().ContainSingle(o => o.NoticeId == "NOTICE-SOON");
    }

    [Fact(Skip = "EF.Functions.DateDiffDay in Select projection is not supported by InMemory provider")]
    public async Task SearchAsync_PaginatesCorrectly()
    {
        SeedMultipleOpportunities(10);

        // Page 1
        var request1 = new OpportunitySearchRequest
        {
            Page = 1,
            PageSize = 4,
            OpenOnly = false
        };

        var result1 = await _service.SearchAsync(request1, organizationId: 1);

        result1.TotalCount.Should().Be(10);
        result1.Items.Count().Should().Be(4);
        result1.HasNextPage.Should().BeTrue();
        result1.HasPreviousPage.Should().BeFalse();

        // Page 3 (last page)
        var request3 = new OpportunitySearchRequest
        {
            Page = 3,
            PageSize = 4,
            OpenOnly = false
        };

        var result3 = await _service.SearchAsync(request3, organizationId: 1);

        result3.Items.Count().Should().Be(2);
        result3.HasNextPage.Should().BeFalse();
        result3.HasPreviousPage.Should().BeTrue();
    }

    // -----------------------------------------------------------------------
    // GetDetailAsync Tests
    // -----------------------------------------------------------------------

    [Fact]
    public async Task GetDetailAsync_ExistingNotice_ReturnsDetail()
    {
        SeedOpportunity("NOTICE-001", title: "IT Services Contract", naicsCode: "541512", setAsideCode: "WOSB");

        var result = await _service.GetDetailAsync("NOTICE-001", organizationId: 1);

        result.Should().NotBeNull();
        result!.NoticeId.Should().Be("NOTICE-001");
        result.Title.Should().Be("IT Services Contract");
        result.NaicsCode.Should().Be("541512");
        result.SetAsideCode.Should().Be("WOSB");
    }

    [Fact]
    public async Task GetDetailAsync_NonexistentNotice_ReturnsNull()
    {
        var result = await _service.GetDetailAsync("NONEXISTENT", organizationId: 1);

        result.Should().BeNull();
    }

    [Fact]
    public async Task GetDetailAsync_IncludesProspectForOrg()
    {
        SeedOpportunity("NOTICE-001");

        _context.Prospects.Add(new Prospect
        {
            OrganizationId = 1,
            NoticeId = "NOTICE-001",
            Status = "REVIEWING",
            Priority = "HIGH",
            CreatedAt = DateTime.UtcNow,
            UpdatedAt = DateTime.UtcNow
        });
        _context.SaveChanges();

        var result = await _service.GetDetailAsync("NOTICE-001", organizationId: 1);

        result.Should().NotBeNull();
        result!.Prospect.Should().NotBeNull();
        result.Prospect!.Status.Should().Be("REVIEWING");
    }

    [Fact]
    public async Task GetDetailAsync_ExcludesProspectFromOtherOrg()
    {
        SeedOpportunity("NOTICE-001");

        _context.Prospects.Add(new Prospect
        {
            OrganizationId = 2,
            NoticeId = "NOTICE-001",
            Status = "REVIEWING",
            CreatedAt = DateTime.UtcNow,
            UpdatedAt = DateTime.UtcNow
        });
        _context.SaveChanges();

        var result = await _service.GetDetailAsync("NOTICE-001", organizationId: 1);

        result.Should().NotBeNull();
        result!.Prospect.Should().BeNull();
    }

    // -----------------------------------------------------------------------
    // GetTargetsAsync is backed by a database view and cannot be tested
    // with InMemory (keyless entity type mapped to v_target_opportunities).
    // -----------------------------------------------------------------------

    // -----------------------------------------------------------------------
    // Phase 100: Type Filtering Tests (SearchAsync)
    //
    // Like the other SearchAsync tests above, these are skipped because
    // EF.Functions.DateDiffDay is not supported by the InMemory provider.
    // They document the expected behavior for integration testing.
    // -----------------------------------------------------------------------

    [Fact(Skip = "EF.Functions.DateDiffDay in Select projection is not supported by InMemory provider")]
    public async Task SearchAsync_ExcludesNonBiddableTypes()
    {
        SeedOpportunity("BIDDABLE-001");
        _context.Opportunities.Add(new Opportunity
        {
            NoticeId = "AWARD-001",
            Title = "Award Notice",
            Type = "Award Notice",
            Active = "Y",
            ResponseDeadline = DateTime.UtcNow.AddDays(30)
        });
        _context.Opportunities.Add(new Opportunity
        {
            NoticeId = "JUST-001",
            Title = "Justification",
            Type = "Justification",
            Active = "Y",
            ResponseDeadline = DateTime.UtcNow.AddDays(30)
        });
        _context.SaveChanges();

        var request = new OpportunitySearchRequest { OpenOnly = false };
        var result = await _service.SearchAsync(request, organizationId: 1);

        result.TotalCount.Should().Be(1);
        result.Items.Should().ContainSingle(o => o.NoticeId == "BIDDABLE-001");
    }

    [Fact(Skip = "EF.Functions.DateDiffDay in Select projection is not supported by InMemory provider")]
    public async Task SearchAsync_EmptyStringSolicitationNumber_NotGrouped()
    {
        // Two opportunities with empty-string solicitation_number should both appear
        _context.Opportunities.Add(new Opportunity
        {
            NoticeId = "EMPTY-SOL-1",
            Title = "Empty Sol 1",
            SolicitationNumber = "",
            PostedDate = new DateOnly(2026, 1, 1),
            Active = "Y",
            ResponseDeadline = DateTime.UtcNow.AddDays(30)
        });
        _context.Opportunities.Add(new Opportunity
        {
            NoticeId = "EMPTY-SOL-2",
            Title = "Empty Sol 2",
            SolicitationNumber = "",
            PostedDate = new DateOnly(2026, 2, 1),
            Active = "Y",
            ResponseDeadline = DateTime.UtcNow.AddDays(30)
        });
        _context.SaveChanges();

        var request = new OpportunitySearchRequest { OpenOnly = false };
        var result = await _service.SearchAsync(request, organizationId: 1);

        result.TotalCount.Should().Be(2, "empty-string solicitation numbers should not be grouped together");
    }

    // -----------------------------------------------------------------------
    // Phase 100: Amendment History Enrichment (GetDetailAsync)
    // -----------------------------------------------------------------------

    [Fact]
    public async Task GetDetailAsync_AmendmentsIncludeAwardeeNameAndAwardAmount()
    {
        // Seed the primary opportunity
        _context.Opportunities.Add(new Opportunity
        {
            NoticeId = "PRIMARY-001",
            Title = "IT Services Contract",
            SolicitationNumber = "SOL-AMEND-TEST",
            // Phase 132: amendment grouping keys off the normalized column (loader-populated).
            SolicitationNumberNormalized = "SOLAMENDTEST",
            Type = "Combined Synopsis/Solicitation",
            PostedDate = new DateOnly(2026, 1, 1),
            Active = "Y"
        });

        // Seed an Award Notice amendment with awardee info. Use a differently-dashed
        // form of the same solicitation number to prove normalized matching works.
        _context.Opportunities.Add(new Opportunity
        {
            NoticeId = "AWARD-AMEND-001",
            Title = "IT Services Contract - Award",
            SolicitationNumber = "SOL-AMEND-TEST",
            SolicitationNumberNormalized = "SOLAMENDTEST",
            Type = "Award Notice",
            PostedDate = new DateOnly(2026, 3, 1),
            AwardeeName = "Tech Solutions Inc",
            AwardAmount = 2_500_000m,
            Active = "Y"
        });
        _context.SaveChanges();

        var result = await _service.GetDetailAsync("PRIMARY-001", organizationId: 1);

        result.Should().NotBeNull();
        result!.Amendments.Should().ContainSingle();
        result.Amendments[0].NoticeId.Should().Be("AWARD-AMEND-001");
        result.Amendments[0].AwardeeName.Should().Be("Tech Solutions Inc");
        result.Amendments[0].AwardAmount.Should().Be(2_500_000m);
    }

    [Fact]
    public async Task GetDetailAsync_AmendmentsWithNullAwardeeFields_ReturnsNull()
    {
        _context.Opportunities.Add(new Opportunity
        {
            NoticeId = "PRIMARY-002",
            Title = "Services Contract",
            SolicitationNumber = "SOL-NULL-AWARD",
            SolicitationNumberNormalized = "SOLNULLAWARD",
            Type = "Solicitation",
            PostedDate = new DateOnly(2026, 1, 1),
            Active = "Y"
        });

        // An amendment that has no awardee info (e.g., a modification, not an award)
        _context.Opportunities.Add(new Opportunity
        {
            NoticeId = "MOD-001",
            Title = "Services Contract - Modification",
            SolicitationNumber = "SOL-NULL-AWARD",
            SolicitationNumberNormalized = "SOLNULLAWARD",
            Type = "Solicitation",
            PostedDate = new DateOnly(2026, 2, 1),
            AwardeeName = null,
            AwardAmount = null,
            Active = "Y"
        });
        _context.SaveChanges();

        var result = await _service.GetDetailAsync("PRIMARY-002", organizationId: 1);

        result.Should().NotBeNull();
        result!.Amendments.Should().ContainSingle();
        result.Amendments[0].AwardeeName.Should().BeNull();
        result.Amendments[0].AwardAmount.Should().BeNull();
    }

    [Fact]
    public async Task GetDetailAsync_NoSolicitationNumber_ReturnsEmptyAmendments()
    {
        _context.Opportunities.Add(new Opportunity
        {
            NoticeId = "NO-SOL-001",
            Title = "Special Notice",
            SolicitationNumber = null,
            Type = "Special Notice",
            Active = "Y"
        });
        _context.SaveChanges();

        var result = await _service.GetDetailAsync("NO-SOL-001", organizationId: 1);

        result.Should().NotBeNull();
        result!.Amendments.Should().BeEmpty();
    }

    [Fact]
    public async Task GetDetailAsync_AmendmentsMatchAcrossDifferentDashFormats()
    {
        // Phase 132: the same identifier filed with different dash formatting must
        // still group as amendments because matching keys off the normalized column.
        _context.Opportunities.Add(new Opportunity
        {
            NoticeId = "DASH-PRIMARY",
            Title = "Dashed primary",
            SolicitationNumber = "FA4484-20-S-C002",
            SolicitationNumberNormalized = "FA448420SC002",
            Type = "Solicitation",
            PostedDate = new DateOnly(2026, 1, 1),
            Active = "Y"
        });
        _context.Opportunities.Add(new Opportunity
        {
            NoticeId = "DASHLESS-AMEND",
            Title = "Dashless amendment",
            SolicitationNumber = "FA448420SC002",
            SolicitationNumberNormalized = "FA448420SC002",
            Type = "Solicitation",
            PostedDate = new DateOnly(2026, 2, 1),
            Active = "Y"
        });
        await _context.SaveChangesAsync();

        var result = await _service.GetDetailAsync("DASH-PRIMARY", organizationId: 1);

        result.Should().NotBeNull();
        // Detail returns the preserved original for display, normalized for cross-ref.
        result!.SolicitationNumber.Should().Be("FA4484-20-S-C002");
        result.SolicitationNumberNormalized.Should().Be("FA448420SC002");
        result.Amendments.Should().ContainSingle(a => a.NoticeId == "DASHLESS-AMEND",
            "the dashless amendment shares the same normalized solicitation number");
    }

    // -----------------------------------------------------------------------
    // ExportCsvAsync Tests (Phase 100)
    //
    // ExportCsvAsync does not use EF.Functions.DateDiffDay, so these can run.
    // -----------------------------------------------------------------------

    [Fact]
    public async Task ExportCsvAsync_ExcludesNonBiddableTypes()
    {
        _context.Opportunities.Add(new Opportunity
        {
            NoticeId = "EXPORT-BIDDABLE",
            Title = "IT Services",
            Type = "Solicitation",
            Active = "Y",
            ResponseDeadline = DateTime.UtcNow.AddDays(30)
        });
        _context.Opportunities.Add(new Opportunity
        {
            NoticeId = "EXPORT-AWARD",
            Title = "Award",
            Type = "Award Notice",
            Active = "Y",
            ResponseDeadline = DateTime.UtcNow.AddDays(30)
        });
        _context.SaveChanges();

        var request = new OpportunitySearchRequest { OpenOnly = false };
        var csv = await _service.ExportCsvAsync(request, organizationId: 1);

        csv.Should().Contain("EXPORT-BIDDABLE");
        csv.Should().NotContain("EXPORT-AWARD");
    }

    [Fact]
    public async Task ExportCsvAsync_DedupsBySolicitationNumber()
    {
        _context.Opportunities.Add(new Opportunity
        {
            NoticeId = "CSV-OLD",
            Title = "Old Version",
            SolicitationNumber = "CSV-SOL-001",
            // Phase 132: dedup keys off the normalized column (loader-populated).
            SolicitationNumberNormalized = "CSVSOL001",
            Type = "Solicitation",
            PostedDate = new DateOnly(2026, 1, 1),
            Active = "Y",
            ResponseDeadline = DateTime.UtcNow.AddDays(30)
        });
        _context.Opportunities.Add(new Opportunity
        {
            NoticeId = "CSV-NEW",
            Title = "New Version",
            SolicitationNumber = "CSV-SOL-001",
            SolicitationNumberNormalized = "CSVSOL001",
            Type = "Solicitation",
            PostedDate = new DateOnly(2026, 3, 1),
            Active = "Y",
            ResponseDeadline = DateTime.UtcNow.AddDays(30)
        });
        _context.SaveChanges();

        var request = new OpportunitySearchRequest { OpenOnly = false };
        var csv = await _service.ExportCsvAsync(request, organizationId: 1);

        csv.Should().Contain("CSV-NEW");
        csv.Should().NotContain("CSV-OLD");
    }

    [Fact]
    public async Task ExportCsvAsync_EmptyStringSolicitationNumber_BothIncluded()
    {
        _context.Opportunities.Add(new Opportunity
        {
            NoticeId = "CSV-EMPTY-1",
            Title = "Empty Sol 1",
            SolicitationNumber = "",
            Type = "Special Notice",
            PostedDate = new DateOnly(2026, 1, 1),
            Active = "Y",
            ResponseDeadline = DateTime.UtcNow.AddDays(30)
        });
        _context.Opportunities.Add(new Opportunity
        {
            NoticeId = "CSV-EMPTY-2",
            Title = "Empty Sol 2",
            SolicitationNumber = "",
            Type = "Special Notice",
            PostedDate = new DateOnly(2026, 2, 1),
            Active = "Y",
            ResponseDeadline = DateTime.UtcNow.AddDays(30)
        });
        _context.SaveChanges();

        var request = new OpportunitySearchRequest { OpenOnly = false };
        var csv = await _service.ExportCsvAsync(request, organizationId: 1);

        csv.Should().Contain("CSV-EMPTY-1");
        csv.Should().Contain("CSV-EMPTY-2");
    }

    // -----------------------------------------------------------------------
    // FetchDescriptionAsync — Phase 123: graceful rate-limit handling
    //
    // When SAM.gov returns HTTP 429 the service must:
    //   - NOT return a generic error
    //   - Insert a DataLoadRequest(DESCRIPTION_FETCH, NOTICE_ID, PENDING)
    //   - Dedup against existing PENDING / PENDING_RETRY rows for the same notice
    //   - Return a FetchDescriptionResult with Queued = true
    // -----------------------------------------------------------------------

    /// <summary>
    /// Stub HttpMessageHandler that returns a fixed HttpResponseMessage for any request.
    /// Used to simulate SAM.gov returning HTTP 429.
    /// </summary>
    private sealed class StubHttpMessageHandler : System.Net.Http.HttpMessageHandler
    {
        private readonly System.Net.HttpStatusCode _status;

        public StubHttpMessageHandler(System.Net.HttpStatusCode status) => _status = status;

        public int CallCount { get; private set; }

        protected override Task<HttpResponseMessage> SendAsync(
            HttpRequestMessage request, CancellationToken cancellationToken)
        {
            CallCount++;
            return Task.FromResult(new HttpResponseMessage(_status)
            {
                Content = new StringContent("{}")
            });
        }
    }

    private static OpportunityService CreateServiceWithStubbedSamApi(
        FedProspectorDbContext context,
        System.Net.HttpStatusCode samStatus,
        out StubHttpMessageHandler handler)
    {
        handler = new StubHttpMessageHandler(samStatus);
        var httpClient = new HttpClient(handler);

        var factoryMock = new Mock<IHttpClientFactory>();
        factoryMock.Setup(f => f.CreateClient("SamApi")).Returns(httpClient);

        var samApiOptions = Options.Create(new SamApiOptions { ApiKey = "test-key" });
        return new OpportunityService(
            context,
            NullLogger<OpportunityService>.Instance,
            factoryMock.Object,
            samApiOptions,
            CreateCompanyProfileServiceMock());
    }

    /// <summary>
    /// Stub ICompanyProfileService for size-eligibility annotation (Phase 129 Unit C).
    /// Returns no eligibility data so search/detail results are left unannotated.
    /// </summary>
    private static ICompanyProfileService CreateCompanyProfileServiceMock()
    {
        var mock = new Mock<ICompanyProfileService>();
        mock.Setup(s => s.CheckSizeEligibilityAsync(It.IsAny<int>(), It.IsAny<IEnumerable<string>>()))
            .ReturnsAsync(new Dictionary<string, SizeEligibilityResultDto>());
        mock.Setup(s => s.CheckSizeEligibilityAsync(It.IsAny<int>(), It.IsAny<string>()))
            .ReturnsAsync((int _, string naics) => new SizeEligibilityResultDto { NaicsCode = naics });
        return mock.Object;
    }

    [Fact]
    public async Task FetchDescriptionAsync_SamReturns429_QueuesRequestAndReturnsQueuedResult()
    {
        const string noticeId = "NOTICE-429";

        _context.Opportunities.Add(new Opportunity
        {
            NoticeId = noticeId,
            Title = "Needs Description",
            DescriptionUrl = "https://api.sam.gov/opportunities/v2/noticedesc?noticeid=NOTICE-429",
            Active = "Y"
        });
        await _context.SaveChangesAsync();

        var service = CreateServiceWithStubbedSamApi(
            _context, System.Net.HttpStatusCode.TooManyRequests, out var handler);

        var result = await service.FetchDescriptionAsync(noticeId, userId: 42);

        handler.CallCount.Should().Be(1, "the service must attempt the SAM.gov call before queuing");

        result.Queued.Should().BeTrue();
        result.Success.Should().BeFalse();
        result.DescriptionText.Should().BeNull();
        result.ErrorMessage.Should().BeNull("queued is not an error");
        result.QueuedMessage.Should().NotBeNullOrWhiteSpace();

        var queued = await _context.DataLoadRequests
            .Where(r => r.RequestType == "DESCRIPTION_FETCH" && r.LookupKey == noticeId)
            .ToListAsync();

        queued.Should().ContainSingle();
        queued[0].LookupKeyType.Should().Be("NOTICE_ID");
        queued[0].Status.Should().Be("PENDING");
        queued[0].RequestedBy.Should().Be(42);
    }

    [Fact]
    public async Task FetchDescriptionAsync_SamReturns429_DoesNotDuplicateExistingPendingRequest()
    {
        const string noticeId = "NOTICE-DEDUP";

        _context.Opportunities.Add(new Opportunity
        {
            NoticeId = noticeId,
            Title = "Needs Description",
            DescriptionUrl = "https://api.sam.gov/opportunities/v2/noticedesc?noticeid=NOTICE-DEDUP",
            Active = "Y"
        });

        // Pre-existing PENDING row — service must skip insert.
        _context.DataLoadRequests.Add(new DataLoadRequest
        {
            RequestType = "DESCRIPTION_FETCH",
            LookupKey = noticeId,
            LookupKeyType = "NOTICE_ID",
            Status = "PENDING",
            RequestedAt = DateTime.UtcNow.AddMinutes(-5)
        });
        await _context.SaveChangesAsync();

        var service = CreateServiceWithStubbedSamApi(
            _context, System.Net.HttpStatusCode.TooManyRequests, out _);

        var result = await service.FetchDescriptionAsync(noticeId, userId: 7);

        result.Queued.Should().BeTrue("controller should still see queued so the UI shows the queued message");

        var count = await _context.DataLoadRequests
            .CountAsync(r => r.RequestType == "DESCRIPTION_FETCH" && r.LookupKey == noticeId);
        count.Should().Be(1, "the existing PENDING row should be reused, not duplicated");
    }

    [Fact]
    public async Task FetchDescriptionAsync_SamReturns429_DedupsAgainstPendingRetry()
    {
        const string noticeId = "NOTICE-RETRY";

        _context.Opportunities.Add(new Opportunity
        {
            NoticeId = noticeId,
            Title = "Needs Description",
            DescriptionUrl = "https://api.sam.gov/opportunities/v2/noticedesc?noticeid=NOTICE-RETRY",
            Active = "Y"
        });
        _context.DataLoadRequests.Add(new DataLoadRequest
        {
            RequestType = "DESCRIPTION_FETCH",
            LookupKey = noticeId,
            LookupKeyType = "NOTICE_ID",
            Status = "PENDING_RETRY",
            RequestedAt = DateTime.UtcNow.AddMinutes(-30)
        });
        await _context.SaveChangesAsync();

        var service = CreateServiceWithStubbedSamApi(
            _context, System.Net.HttpStatusCode.TooManyRequests, out _);

        var result = await service.FetchDescriptionAsync(noticeId, userId: null);

        result.Queued.Should().BeTrue();

        var count = await _context.DataLoadRequests
            .CountAsync(r => r.RequestType == "DESCRIPTION_FETCH" && r.LookupKey == noticeId);
        count.Should().Be(1);
    }

    [Fact]
    public async Task FetchDescriptionAsync_NoOpportunity_ReturnsNotFound_DoesNotQueue()
    {
        var service = CreateServiceWithStubbedSamApi(
            _context, System.Net.HttpStatusCode.TooManyRequests, out var handler);

        var result = await service.FetchDescriptionAsync("DOES-NOT-EXIST", userId: 1);

        result.NotFound.Should().BeTrue();
        result.Queued.Should().BeFalse();
        result.Success.Should().BeFalse();
        handler.CallCount.Should().Be(0, "no opportunity means no SAM.gov call");

        var queued = await _context.DataLoadRequests.CountAsync();
        queued.Should().Be(0);
    }

    [Fact]
    public async Task FetchDescriptionAsync_CachedDescription_ReturnsSuccessWithoutCallingSam()
    {
        const string noticeId = "NOTICE-CACHED";

        _context.Opportunities.Add(new Opportunity
        {
            NoticeId = noticeId,
            Title = "Has Description",
            DescriptionText = "Already fetched description text.",
            Active = "Y"
        });
        await _context.SaveChangesAsync();

        var service = CreateServiceWithStubbedSamApi(
            _context, System.Net.HttpStatusCode.TooManyRequests, out var handler);

        var result = await service.FetchDescriptionAsync(noticeId, userId: 1);

        result.Success.Should().BeTrue();
        result.Queued.Should().BeFalse();
        result.DescriptionText.Should().Be("Already fetched description text.");
        handler.CallCount.Should().Be(0, "cached text should bypass the SAM.gov call");
    }

    [Fact]
    public async Task FetchDescriptionAsync_SamReturns500_ReturnsErrorNotQueued()
    {
        const string noticeId = "NOTICE-500";

        _context.Opportunities.Add(new Opportunity
        {
            NoticeId = noticeId,
            Title = "Needs Description",
            DescriptionUrl = "https://api.sam.gov/opportunities/v2/noticedesc?noticeid=NOTICE-500",
            Active = "Y"
        });
        await _context.SaveChangesAsync();

        var service = CreateServiceWithStubbedSamApi(
            _context, System.Net.HttpStatusCode.InternalServerError, out _);

        var result = await service.FetchDescriptionAsync(noticeId, userId: 1);

        result.Queued.Should().BeFalse("only 429 should queue — 500 is a generic error");
        result.Success.Should().BeFalse();
        result.ErrorMessage.Should().NotBeNull();

        var queued = await _context.DataLoadRequests.CountAsync();
        queued.Should().Be(0);
    }
}
