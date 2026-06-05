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
        // Phase 136 follow-up: RecommendedOpportunityService now resolves linked-entity
        // NAICS via IOrganizationEntityService. A real OrganizationEntityService over the
        // same in-memory context returns an empty set for orgs with no links, so existing
        // scenarios are unaffected.
        var orgEntityService = new OrganizationEntityService(
            _context, NullLogger<OrganizationEntityService>.Instance);
        _service = new RecommendedOpportunityService(
            _context, orgEntityService, NullLogger<RecommendedOpportunityService>.Instance);

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

    private void SeedAttachmentSummary(
        string noticeId,
        string? clearanceRequired = null,
        string overallConfidence = "low",
        string? isRecompete = null,
        string? incumbentName = null)
    {
        _context.OpportunityAttachmentSummaries.Add(new OpportunityAttachmentSummary
        {
            NoticeId = noticeId,
            ExtractionMethod = "ai",
            ClearanceRequired = clearanceRequired,
            OverallConfidence = overallConfidence,
            IsRecompete = isRecompete,
            IncumbentName = incumbentName,
            ExtractedAt = DateTime.UtcNow
        });
        _context.SaveChanges();
    }

    /// <summary>
    /// Phase 136 follow-up: seed an ACTIVE linked entity for OrgId with a single
    /// entity_naics row, so its NAICS participates in candidate selection / scoring.
    /// </summary>
    private void SeedLinkedEntityWithNaics(string uei, string naicsCode, string relationship = "JV_PARTNER")
    {
        _context.OrganizationEntities.Add(new OrganizationEntity
        {
            OrganizationId = OrgId,
            UeiSam = uei,
            Relationship = relationship,
            IsActive = "Y",
            CreatedAt = DateTime.UtcNow,
            UpdatedAt = DateTime.UtcNow
        });
        _context.EntityNaicsCodes.Add(new EntityNaics
        {
            UeiSam = uei,
            NaicsCode = naicsCode,
            IsPrimary = "N"
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

    // -----------------------------------------------------------------------
    // Phase 136 Unit B — High-confidence clearance filter
    // -----------------------------------------------------------------------

    [Fact]
    public async Task GetRecommendedAsync_HiddenByDefault_ExcludesHighConfidenceClearance()
    {
        SeedOpportunity("NO-CLEAR-001");
        SeedOpportunity("CLEAR-HIGH-001");
        SeedAttachmentSummary("CLEAR-HIGH-001", clearanceRequired: "Y", overallConfidence: "high");

        var results = await _service.GetRecommendedAsync(OrgId, limit: 100);

        results.Should().ContainSingle(r => r.NoticeId == "NO-CLEAR-001");
        results.Should().NotContain(r => r.NoticeId == "CLEAR-HIGH-001");
    }

    [Fact]
    public async Task GetRecommendedAsync_LowConfidenceClearance_IsNotExcluded()
    {
        // clearance_required=Y but only low confidence — must NOT be filtered out
        SeedOpportunity("CLEAR-LOW-001");
        SeedAttachmentSummary("CLEAR-LOW-001", clearanceRequired: "Y", overallConfidence: "low");

        var results = await _service.GetRecommendedAsync(OrgId, limit: 100);

        results.Should().ContainSingle(r => r.NoticeId == "CLEAR-LOW-001");
        results[0].ClearanceRequired.Should().BeFalse();
    }

    [Fact]
    public async Task GetRecommendedAsync_IncludeClearance_AppendsAsSeparateFlaggedGroup()
    {
        SeedOpportunity("NO-CLEAR-001");
        SeedOpportunity("CLEAR-HIGH-001");
        SeedAttachmentSummary("CLEAR-HIGH-001", clearanceRequired: "Y", overallConfidence: "high");

        var results = await _service.GetRecommendedAsync(
            OrgId, limit: 100, includeClearanceRequired: true);

        results.Should().Contain(r => r.NoticeId == "NO-CLEAR-001");
        var clearance = results.Should().ContainSingle(r => r.NoticeId == "CLEAR-HIGH-001").Subject;
        clearance.ClearanceRequired.Should().BeTrue();
    }

    [Fact]
    public async Task GetRecommendedAsync_ClearanceDoesNotConsumeTopNSlots()
    {
        // Top-N is computed over the clearance-excluded set, so a small limit still
        // returns `limit` non-clearance items even when clearance items exist.
        for (int i = 1; i <= 3; i++)
            SeedOpportunity($"OPEN-{i:D2}", solicitationNumber: $"SOL-OPEN-{i:D2}");

        SeedOpportunity("CLEAR-HIGH-001", solicitationNumber: "SOL-CLEAR");
        SeedAttachmentSummary("CLEAR-HIGH-001", clearanceRequired: "Y", overallConfidence: "high");

        var results = await _service.GetRecommendedAsync(
            OrgId, limit: 2, includeClearanceRequired: true);

        // 2 ranked (clearance-excluded) + 1 appended clearance group = 3
        results.Count(r => !r.ClearanceRequired).Should().Be(2);
        results.Should().ContainSingle(r => r.ClearanceRequired);
    }

    // -----------------------------------------------------------------------
    // Phase 136 Unit C — Market Research (ungated Sources Sought / Special Notice)
    // -----------------------------------------------------------------------

    [Fact]
    public async Task GetMarketResearchAsync_ReturnsOnlySourcesSoughtAndSpecialNotice()
    {
        SeedOpportunity("SS-001", type: "Sources Sought", solicitationNumber: "SOL-SS");
        SeedOpportunity("SN-001", type: "Special Notice", solicitationNumber: "SOL-SN");
        SeedOpportunity("SOL-001", type: "Solicitation", solicitationNumber: "SOL-SOL");
        SeedOpportunity("PRESOL-001", type: "Presolicitation", solicitationNumber: "SOL-PRE");

        var results = await _service.GetMarketResearchAsync(OrgId);

        results.Select(r => r.NoticeId).Should().BeEquivalentTo(["SS-001", "SN-001"]);
    }

    [Fact]
    public async Task GetMarketResearchAsync_NotScored_OqScoreNull()
    {
        SeedOpportunity("SS-001", type: "Sources Sought");

        var results = await _service.GetMarketResearchAsync(OrgId);

        results.Should().ContainSingle();
        results[0].OqScore.Should().BeNull();
        results[0].OqScoreCategory.Should().Be("MarketResearch");
    }

    [Fact]
    public async Task GetMarketResearchAsync_AppliesSetAsideCertFilter()
    {
        // Org holds WOSB only. An 8(a) set-aside Sources Sought must be filtered out.
        SeedOpportunity("SS-WOSB", type: "Sources Sought", setAsideCode: "WOSB",
            solicitationNumber: "SOL-WOSB");
        SeedOpportunity("SS-8A", type: "Sources Sought", setAsideCode: "8A",
            solicitationNumber: "SOL-8A");

        var results = await _service.GetMarketResearchAsync(OrgId);

        results.Should().ContainSingle(r => r.NoticeId == "SS-WOSB");
        results.Should().NotContain(r => r.NoticeId == "SS-8A");
    }

    // -----------------------------------------------------------------------
    // Phase 136 Unit D — Score renormalization over real-data factors
    // -----------------------------------------------------------------------

    [Fact]
    public async Task CalculateOqScoreAsync_RenormalizesOverRealDataFactors()
    {
        // With no award/past-performance/competition data, several factors fall back to
        // defaults (HadRealData=false). The returned OqScore must equal the weighted
        // average of ONLY the real-data factors (their weights renormalized to 1.0),
        // never the raw weighted sum that includes default factors.
        SeedOpportunity("SCORE-001", setAsideCode: "WOSB");

        var dto = await _service.CalculateOqScoreAsync("SCORE-001", OrgId);

        dto.Should().NotBeNull();
        dto!.OqScore.Should().NotBeNull();

        var realFactors = dto.OqScoreFactors.Where(f => f.HadRealData).ToList();
        realFactors.Should().NotBeEmpty();

        var presentWeight = realFactors.Sum(f => f.Weight);
        var expected = Math.Round(realFactors.Sum(f => f.Score * f.Weight) / presentWeight, 1);
        dto.OqScore.Should().Be(expected);
    }

    // -----------------------------------------------------------------------
    // Phase 136 follow-up — Linked-entity NAICS inclusion
    // -----------------------------------------------------------------------

    [Fact]
    public async Task GetRecommendedAsync_IncludesOppInLinkedEntityNaics()
    {
        // Org is registered only for 541512. A linked JV partner carries 238210.
        // An opportunity in 238210 must surface purely on the linked-entity NAICS.
        SeedLinkedEntityWithNaics("UEI_JV_00001", "238210");
        SeedOpportunity("LINKED-238210", naicsCode: "238210");

        var results = await _service.GetRecommendedAsync(OrgId, limit: 100);

        results.Should().ContainSingle(r => r.NoticeId == "LINKED-238210");
    }

    [Fact]
    public async Task GetRecommendedAsync_LinkedEntityNaics_ScoredAsLinkedEntityTier()
    {
        SeedLinkedEntityWithNaics("UEI_JV_00001", "238210");
        SeedOpportunity("LINKED-238210", naicsCode: "238210");

        var results = await _service.GetRecommendedAsync(OrgId, limit: 100);

        var dto = results.Single(r => r.NoticeId == "LINKED-238210");
        var profile = dto.OqScoreFactors.Single(f => f.Name == "Profile Match");
        profile.Detail.Should().Be("Linked-entity NAICS match");
        profile.Score.Should().Be(55);
    }

    [Fact]
    public async Task GetRecommendedAsync_RegisteredNaics_KeepsRegisteredTierEvenIfAlsoLinkedEntity()
    {
        // 541512 is the org's PRIMARY registered NAICS AND (redundantly) a linked-entity
        // NAICS. Registered membership must win — primary tier, not linked-entity tier.
        SeedLinkedEntityWithNaics("UEI_JV_00001", "541512");
        SeedOpportunity("REG-541512", naicsCode: "541512");

        var results = await _service.GetRecommendedAsync(OrgId, limit: 100);

        var dto = results.Single(r => r.NoticeId == "REG-541512");
        var profile = dto.OqScoreFactors.Single(f => f.Name == "Profile Match");
        profile.Score.Should().Be(100);
        profile.Detail.Should().Be("Primary NAICS + cert match");
    }

    [Fact]
    public async Task CalculateOqScoreAsync_LinkedEntityNaics_ScoredAsLinkedEntityTier()
    {
        SeedLinkedEntityWithNaics("UEI_JV_00001", "238210");
        SeedOpportunity("LINKED-238210", naicsCode: "238210");

        var dto = await _service.CalculateOqScoreAsync("LINKED-238210", OrgId);

        dto.Should().NotBeNull();
        var profile = dto!.OqScoreFactors.Single(f => f.Name == "Profile Match");
        profile.Detail.Should().Be("Linked-entity NAICS match");
        profile.Score.Should().Be(55);
    }
}
