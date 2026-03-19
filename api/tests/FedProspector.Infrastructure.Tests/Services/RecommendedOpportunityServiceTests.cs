using FedProspector.Core.Models;
using FedProspector.Infrastructure.Data;
using FedProspector.Infrastructure.Services;
using FluentAssertions;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging.Abstractions;

namespace FedProspector.Infrastructure.Tests.Services;

public class RecommendedOpportunityServiceTests : IDisposable
{
    private readonly FedProspectorDbContext _context;
    private readonly RecommendedOpportunityService _service;
    private const int OrgId = 1;

    public RecommendedOpportunityServiceTests()
    {
        var options = new DbContextOptionsBuilder<FedProspectorDbContext>()
            .UseInMemoryDatabase(databaseName: Guid.NewGuid().ToString())
            .Options;

        _context = new FedProspectorDbContext(options);
        _service = new RecommendedOpportunityService(_context, NullLogger<RecommendedOpportunityService>.Instance);

        // Seed org with NAICS and certification so recommendations can be generated
        SeedOrganization();
    }

    public void Dispose()
    {
        _context.Dispose();
    }

    // -----------------------------------------------------------------------
    // Seed Helpers
    // -----------------------------------------------------------------------

    private void SeedOrganization()
    {
        _context.Organizations.Add(new Organization
        {
            OrganizationId = OrgId,
            Name = "Test Org",
            Slug = "test-org",
            CreatedAt = DateTime.UtcNow,
            UpdatedAt = DateTime.UtcNow
        });

        _context.OrganizationNaics.Add(new OrganizationNaics
        {
            OrganizationId = OrgId,
            NaicsCode = "541512",
            IsPrimary = "Y",
            SizeStandardMet = "Y",
            CreatedAt = DateTime.UtcNow
        });

        _context.OrganizationCertifications.Add(new OrganizationCertification
        {
            OrganizationId = OrgId,
            CertificationType = "WOSB",
            IsActive = "Y",
            CreatedAt = DateTime.UtcNow
        });

        _context.SaveChanges();
    }

    private void SeedOpportunity(
        string noticeId,
        string? title = null,
        string? type = null,
        string? naicsCode = "541512",
        string? solicitationNumber = null,
        DateOnly? postedDate = null,
        DateTime? responseDeadline = null,
        string? active = "Y",
        string? setAsideCode = null,
        decimal? awardAmount = null)
    {
        _context.Opportunities.Add(new Opportunity
        {
            NoticeId = noticeId,
            Title = title ?? $"Opportunity {noticeId}",
            Type = type ?? "Combined Synopsis/Solicitation",
            NaicsCode = naicsCode,
            SolicitationNumber = solicitationNumber,
            PostedDate = postedDate ?? DateOnly.FromDateTime(DateTime.UtcNow),
            ResponseDeadline = responseDeadline ?? DateTime.UtcNow.AddDays(30),
            Active = active,
            SetAsideCode = setAsideCode,
            AwardAmount = awardAmount
        });
        _context.SaveChanges();
    }

    // -----------------------------------------------------------------------
    // Type Filtering Tests (100-1)
    // -----------------------------------------------------------------------

    [Fact]
    public async Task GetRecommendedAsync_ExcludesAwardNotices()
    {
        SeedOpportunity("BIDDABLE-001", type: "Combined Synopsis/Solicitation");
        SeedOpportunity("AWARD-001", type: "Award Notice");

        var results = await _service.GetRecommendedAsync(OrgId, limit: 100);

        results.Should().ContainSingle(r => r.NoticeId == "BIDDABLE-001");
        results.Should().NotContain(r => r.NoticeId == "AWARD-001");
    }

    [Fact]
    public async Task GetRecommendedAsync_ExcludesJustifications()
    {
        SeedOpportunity("BIDDABLE-001", type: "Solicitation");
        SeedOpportunity("JUSTIFICATION-001", type: "Justification");

        var results = await _service.GetRecommendedAsync(OrgId, limit: 100);

        results.Should().ContainSingle(r => r.NoticeId == "BIDDABLE-001");
        results.Should().NotContain(r => r.NoticeId == "JUSTIFICATION-001");
    }

    [Fact]
    public async Task GetRecommendedAsync_ExcludesSaleOfSurplusProperty()
    {
        SeedOpportunity("BIDDABLE-001", type: "Presolicitation");
        SeedOpportunity("SURPLUS-001", type: "Sale of Surplus Property");

        var results = await _service.GetRecommendedAsync(OrgId, limit: 100);

        results.Should().ContainSingle(r => r.NoticeId == "BIDDABLE-001");
        results.Should().NotContain(r => r.NoticeId == "SURPLUS-001");
    }

    [Fact]
    public async Task GetRecommendedAsync_ExcludesConsolidateBundle()
    {
        SeedOpportunity("BIDDABLE-001", type: "Sources Sought");
        SeedOpportunity("BUNDLE-001", type: "Consolidate/(Substantially) Bundle");

        var results = await _service.GetRecommendedAsync(OrgId, limit: 100);

        results.Should().ContainSingle(r => r.NoticeId == "BIDDABLE-001");
        results.Should().NotContain(r => r.NoticeId == "BUNDLE-001");
    }

    [Fact]
    public async Task GetRecommendedAsync_ExcludesAllNonBiddableTypes()
    {
        SeedOpportunity("BIDDABLE-001", type: "Combined Synopsis/Solicitation");
        SeedOpportunity("AWARD-001", type: "Award Notice");
        SeedOpportunity("JUSTIFICATION-001", type: "Justification");
        SeedOpportunity("SURPLUS-001", type: "Sale of Surplus Property");
        SeedOpportunity("BUNDLE-001", type: "Consolidate/(Substantially) Bundle");

        var results = await _service.GetRecommendedAsync(OrgId, limit: 100);

        results.Should().ContainSingle();
        results[0].NoticeId.Should().Be("BIDDABLE-001");
    }

    [Theory]
    [InlineData("Combined Synopsis/Solicitation")]
    [InlineData("Solicitation")]
    [InlineData("Presolicitation")]
    [InlineData("Sources Sought")]
    [InlineData("Special Notice")]
    public async Task GetRecommendedAsync_IncludesBiddableTypes(string biddableType)
    {
        SeedOpportunity("BIDDABLE-001", type: biddableType);

        var results = await _service.GetRecommendedAsync(OrgId, limit: 100);

        results.Should().ContainSingle(r => r.NoticeId == "BIDDABLE-001");
    }

    // -----------------------------------------------------------------------
    // Solicitation-Level Dedup Tests (100-2)
    // -----------------------------------------------------------------------

    [Fact]
    public async Task GetRecommendedAsync_DedupsBySolicitationNumber_KeepsLatestPostedDate()
    {
        // Two notices for the same solicitation — service should keep only the latest
        SeedOpportunity("NOTICE-OLD", solicitationNumber: "SOL-001",
            postedDate: new DateOnly(2026, 1, 1));
        SeedOpportunity("NOTICE-NEW", solicitationNumber: "SOL-001",
            postedDate: new DateOnly(2026, 3, 1));

        var results = await _service.GetRecommendedAsync(OrgId, limit: 100);

        results.Should().ContainSingle();
        results[0].NoticeId.Should().Be("NOTICE-NEW");
    }

    [Fact]
    public async Task GetRecommendedAsync_DedupKeepsMultipleSolicitations()
    {
        // Different solicitation numbers should each keep their latest
        SeedOpportunity("SOL1-OLD", solicitationNumber: "SOL-001",
            postedDate: new DateOnly(2026, 1, 1));
        SeedOpportunity("SOL1-NEW", solicitationNumber: "SOL-001",
            postedDate: new DateOnly(2026, 3, 1));
        SeedOpportunity("SOL2-ONLY", solicitationNumber: "SOL-002",
            postedDate: new DateOnly(2026, 2, 1));

        var results = await _service.GetRecommendedAsync(OrgId, limit: 100);

        results.Should().HaveCount(2);
        results.Select(r => r.NoticeId).Should().Contain("SOL1-NEW");
        results.Select(r => r.NoticeId).Should().Contain("SOL2-ONLY");
    }

    [Fact]
    public async Task GetRecommendedAsync_NullSolicitationNumber_TreatedAsUnique()
    {
        // Each null solicitation_number row should be treated as its own group
        SeedOpportunity("NULL-SOL-1", solicitationNumber: null,
            postedDate: new DateOnly(2026, 1, 1));
        SeedOpportunity("NULL-SOL-2", solicitationNumber: null,
            postedDate: new DateOnly(2026, 2, 1));

        var results = await _service.GetRecommendedAsync(OrgId, limit: 100);

        results.Should().HaveCount(2);
        results.Select(r => r.NoticeId).Should().Contain("NULL-SOL-1");
        results.Select(r => r.NoticeId).Should().Contain("NULL-SOL-2");
    }

    [Fact]
    public async Task GetRecommendedAsync_EmptyStringSolicitationNumber_TreatedAsUnique()
    {
        // Empty-string solicitation_number (231 real rows) must not be grouped together
        SeedOpportunity("EMPTY-SOL-1", solicitationNumber: "",
            postedDate: new DateOnly(2026, 1, 1));
        SeedOpportunity("EMPTY-SOL-2", solicitationNumber: "",
            postedDate: new DateOnly(2026, 2, 1));

        var results = await _service.GetRecommendedAsync(OrgId, limit: 100);

        results.Should().HaveCount(2);
        results.Select(r => r.NoticeId).Should().Contain("EMPTY-SOL-1");
        results.Select(r => r.NoticeId).Should().Contain("EMPTY-SOL-2");
    }

    [Fact]
    public async Task GetRecommendedAsync_TiedPostedDate_UsesNoticeIdAsTiebreaker()
    {
        // Same solicitation, same posted_date — should pick the one with the
        // lexicographically later notice_id (descending sort)
        var sameDate = new DateOnly(2026, 3, 1);
        SeedOpportunity("NOTICE-AAA", solicitationNumber: "SOL-TIED",
            postedDate: sameDate);
        SeedOpportunity("NOTICE-ZZZ", solicitationNumber: "SOL-TIED",
            postedDate: sameDate);

        var results = await _service.GetRecommendedAsync(OrgId, limit: 100);

        results.Should().ContainSingle();
        results[0].NoticeId.Should().Be("NOTICE-ZZZ",
            "ThenByDescending(NoticeId) should pick the later notice_id as tiebreaker");
    }

    // -----------------------------------------------------------------------
    // Combined Type Filter + Dedup Tests
    // -----------------------------------------------------------------------

    [Fact]
    public async Task GetRecommendedAsync_TypeFilterAppliedBeforeDedup()
    {
        // If an Award Notice is the latest for a solicitation, the type filter
        // should exclude it, and dedup should then pick the next-latest biddable notice
        SeedOpportunity("SOL-BIDDABLE", solicitationNumber: "SOL-MIX",
            type: "Combined Synopsis/Solicitation",
            postedDate: new DateOnly(2026, 1, 1));
        SeedOpportunity("SOL-AWARD", solicitationNumber: "SOL-MIX",
            type: "Award Notice",
            postedDate: new DateOnly(2026, 3, 1));

        var results = await _service.GetRecommendedAsync(OrgId, limit: 100);

        results.Should().ContainSingle();
        results[0].NoticeId.Should().Be("SOL-BIDDABLE",
            "Award Notice should be filtered out first, leaving the biddable notice");
    }

    [Fact]
    public async Task GetRecommendedAsync_GsaMasMonster_OnlySurvivesOneRow()
    {
        // Regression canary: solicitation with many Award Notices and one Combined Synopsis
        // mirrors the GSA MAS case (695 rows, 694 Award Notices + 1 biddable)
        var sol = "47QSMD20R0001";
        SeedOpportunity("GSA-BIDDABLE", solicitationNumber: sol,
            type: "Combined Synopsis/Solicitation",
            postedDate: new DateOnly(2025, 6, 1));

        for (int i = 1; i <= 10; i++)
        {
            SeedOpportunity($"GSA-AWARD-{i:D3}", solicitationNumber: sol,
                type: "Award Notice",
                postedDate: new DateOnly(2025, 7, 1));
        }

        var results = await _service.GetRecommendedAsync(OrgId, limit: 100);

        results.Should().ContainSingle();
        results[0].NoticeId.Should().Be("GSA-BIDDABLE");
    }

    // -----------------------------------------------------------------------
    // Edge Case Tests
    // -----------------------------------------------------------------------

    [Fact]
    public async Task GetRecommendedAsync_InactiveOpportunities_AreExcluded()
    {
        SeedOpportunity("ACTIVE-001", active: "Y");
        SeedOpportunity("INACTIVE-001", active: "N");

        var results = await _service.GetRecommendedAsync(OrgId, limit: 100);

        results.Should().ContainSingle(r => r.NoticeId == "ACTIVE-001");
    }

    [Fact]
    public async Task GetRecommendedAsync_ExpiredDeadline_AreExcluded()
    {
        SeedOpportunity("OPEN-001", responseDeadline: DateTime.UtcNow.AddDays(30));
        SeedOpportunity("EXPIRED-001", responseDeadline: DateTime.UtcNow.AddDays(-1));

        var results = await _service.GetRecommendedAsync(OrgId, limit: 100);

        results.Should().ContainSingle(r => r.NoticeId == "OPEN-001");
    }

    [Fact]
    public async Task GetRecommendedAsync_NoOrgNaics_ReturnsEmpty()
    {
        // Org 999 has no NAICS codes
        SeedOpportunity("SOME-001");

        var results = await _service.GetRecommendedAsync(orgId: 999, limit: 100);

        results.Should().BeEmpty();
    }

    [Fact]
    public async Task GetRecommendedAsync_LimitClampedToMax100()
    {
        // Seed more than 100 opportunities
        for (int i = 1; i <= 110; i++)
        {
            SeedOpportunity($"BULK-{i:D4}",
                solicitationNumber: $"SOL-{i:D4}",
                responseDeadline: DateTime.UtcNow.AddDays(30 + i));
        }

        var results = await _service.GetRecommendedAsync(OrgId, limit: 200);

        results.Should().HaveCount(100, "limit should be clamped to 100");
    }

    [Fact]
    public async Task GetRecommendedAsync_LimitClampedToMin1()
    {
        SeedOpportunity("ONLY-001");

        var results = await _service.GetRecommendedAsync(OrgId, limit: 0);

        results.Should().HaveCount(1, "limit 0 should be clamped to 1");
    }
}
