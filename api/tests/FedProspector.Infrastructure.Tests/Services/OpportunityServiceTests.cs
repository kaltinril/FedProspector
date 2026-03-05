using FedProspector.Core.DTOs.Opportunities;
using FedProspector.Core.Models;
using FedProspector.Infrastructure.Data;
using FedProspector.Infrastructure.Services;
using FluentAssertions;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging.Abstractions;

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
        _service = new OpportunityService(_context, NullLogger<OpportunityService>.Instance);
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
}
