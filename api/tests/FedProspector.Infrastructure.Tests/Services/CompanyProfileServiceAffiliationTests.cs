using FedProspector.Core.Models;
using FedProspector.Infrastructure.Data;
using FedProspector.Infrastructure.Services;
using FluentAssertions;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging.Abstractions;

namespace FedProspector.Infrastructure.Tests.Services;

/// <summary>
/// Unit tests for the Phase 133 Task 6 SBA affiliation size roll-up
/// (<see cref="CompanyProfileService.CheckSizeEligibilityWithAffiliatesAsync"/>, 13 CFR 121.103).
///
/// This is the highest-risk code in Phase 133: a false "small" determination on the COMBINED
/// (org + affiliates) figure can lead to false self-certification (False Claims Act exposure).
/// The tests therefore lock down the acceptance criteria the QA flagged as untested:
///   - combined is a SUM, not a MAX (both "M" receipts and "E" employees, with unit conversion);
///   - the inclusion set (SELF via org figures, SISTER_SUBSIDIARY, JV_PARTNER);
///   - TEAMING excluded with reason TEAMING;
///   - approved-MPA JV excluded with reason APPROVED_MPA (and unflagged JV still summed);
///   - missing affiliate data reported as a GAP, never silently treated as zero;
///   - flippedToOtherThanSmall semantics;
///   - additive behavior — the Phase 129 standalone engine result is unchanged;
///   - inactive links ignored;
///   - org missing its own figure for the size_type.
///
/// Harness mirrors the existing OrganizationEntityServiceTests / OrganizationServiceTests:
/// in-memory EF Core DbContext (unique DB per test class instance), NullLogger, FluentAssertions.
/// </summary>
public class CompanyProfileServiceAffiliationTests : IDisposable
{
    private readonly FedProspectorDbContext _context;
    private readonly CompanyProfileService _service;

    // A receipts-based ("M") NAICS standard: threshold stored in $millions.
    private const string RevenueNaics = "541512";
    private const decimal RevenueThresholdMillions = 41.5m; // $41.5M cap

    // An employee-based ("E") NAICS standard: threshold is a headcount.
    private const string EmployeeNaics = "336411";
    private const decimal EmployeeThreshold = 1500m; // 1,500 employees cap

    public CompanyProfileServiceAffiliationTests()
    {
        var options = new DbContextOptionsBuilder<FedProspectorDbContext>()
            .UseInMemoryDatabase(databaseName: Guid.NewGuid().ToString())
            .Options;

        _context = new FedProspectorDbContext(options);
        _service = new CompanyProfileService(_context, NullLogger<CompanyProfileService>.Instance);
    }

    public void Dispose() => _context.Dispose();

    // -----------------------------------------------------------------------
    // Seed helpers
    // -----------------------------------------------------------------------

    private Organization SeedOrganization(
        int orgId = 1,
        decimal? annualRevenue = null,
        int? employeeCount = null)
    {
        var org = new Organization
        {
            OrganizationId = orgId,
            Name = "Test Org",
            Slug = $"test-org-{orgId}",
            IsActive = "Y",
            MaxUsers = 10,
            SubscriptionTier = "trial",
            AnnualRevenue = annualRevenue,
            EmployeeCount = employeeCount,
            CreatedAt = DateTime.UtcNow,
            UpdatedAt = DateTime.UtcNow
        };
        _context.Organizations.Add(org);
        _context.SaveChanges();
        return org;
    }

    /// <summary>Seed an SBA size standard. effectiveDate lets us prove "latest wins".</summary>
    private void SeedSizeStandard(
        string naicsCode,
        string sizeType,
        decimal? sizeStandard,
        DateOnly? effectiveDate = null)
    {
        _context.RefSbaSizeStandards.Add(new RefSbaSizeStandard
        {
            NaicsCode = naicsCode,
            SizeType = sizeType,
            SizeStandard = sizeStandard,
            IndustryDescription = $"Industry {naicsCode}",
            EffectiveDate = effectiveDate ?? new DateOnly(2024, 1, 1),
            CreatedAt = DateTime.UtcNow
        });
        _context.SaveChanges();
    }

    private OrganizationEntity SeedLink(
        int orgId,
        string uei,
        string relationship,
        bool active = true,
        decimal? affiliateAnnualRevenue = null,
        int? affiliateEmployeeCount = null,
        string mpaApproved = "N")
    {
        var link = new OrganizationEntity
        {
            OrganizationId = orgId,
            UeiSam = uei,
            Relationship = relationship,
            IsActive = active ? "Y" : "N",
            AffiliateAnnualRevenue = affiliateAnnualRevenue,
            AffiliateEmployeeCount = affiliateEmployeeCount,
            MpaApproved = mpaApproved,
            CreatedAt = DateTime.UtcNow,
            UpdatedAt = DateTime.UtcNow
        };
        _context.OrganizationEntities.Add(link);
        _context.SaveChanges();
        return link;
    }

    // =======================================================================
    // Combined = SUM (not MAX) — revenue "M" with unit conversion
    // =======================================================================

    [Fact]
    public async Task Revenue_OrgPlusOneIncludedAffiliate_CombinesAsSum_NotMax()
    {
        // Org alone: $20M (small). Affiliate: $30M. Each is individually <= 41.5M cap,
        // so a MAX would call the enterprise "small". The SUM is 50M > 41.5M => NOT small.
        // This is the load-bearing assertion: a sum, never a max.
        SeedOrganization(annualRevenue: 20_000_000m);
        SeedSizeStandard(RevenueNaics, "M", RevenueThresholdMillions);
        SeedLink(1, "UEI_SISTER01", "SISTER_SUBSIDIARY", affiliateAnnualRevenue: 30_000_000m);

        var result = await _service.CheckSizeEligibilityWithAffiliatesAsync(1, RevenueNaics);

        result.SizeType.Should().Be("M");
        result.Threshold.Should().Be(RevenueThresholdMillions);
        // Combined receipts reported in $millions: 20 + 30 = 50.
        result.CombinedRevenue.Should().Be(50m, "combined receipts must be the SUM (20 + 30), not the MAX (30)");
        result.CombinedEmployees.Should().BeNull("employees are not used for an 'M' standard");
        result.StandaloneEligible.Should().BeTrue("$20M alone is under the $41.5M cap");
        result.AffiliatedEligible.Should().BeFalse("combined $50M exceeds the $41.5M cap");
        result.AffiliateCount.Should().Be(1);
    }

    [Fact]
    public async Task Revenue_AppliesMillionsConversion_ConsistentlyToOrgAndAffiliate()
    {
        // Pin the /1,000,000 conversion: raw USD in, $millions out, applied to BOTH inputs.
        // Org $12,300,000 => 12.3M; affiliate $7,250,000 => 7.25M; combined 19.55M.
        SeedOrganization(annualRevenue: 12_300_000m);
        SeedSizeStandard(RevenueNaics, "M", RevenueThresholdMillions);
        SeedLink(1, "UEI_SISTER01", "SISTER_SUBSIDIARY", affiliateAnnualRevenue: 7_250_000m);

        var result = await _service.CheckSizeEligibilityWithAffiliatesAsync(1, RevenueNaics);

        result.CombinedRevenue.Should().Be(19.55m, "both org and affiliate USD figures must be divided by 1,000,000");
        var included = result.IncludedAffiliates.Single();
        included.ContributedAmount.Should().Be(7.25m, "affiliate contribution is reported in $millions");
        result.AffiliatedEligible.Should().BeTrue("19.55M is under the 41.5M cap");
    }

    [Fact]
    public async Task Revenue_MultipleIncludedAffiliates_AllSummedWithOrg()
    {
        // Org 10M + sister 8M + JV 9M = 27M (under 41.5M).
        // Proves the roll-up accumulates across more than one affiliate.
        SeedOrganization(annualRevenue: 10_000_000m);
        SeedSizeStandard(RevenueNaics, "M", RevenueThresholdMillions);
        SeedLink(1, "UEI_SISTER01", "SISTER_SUBSIDIARY", affiliateAnnualRevenue: 8_000_000m);
        SeedLink(1, "UEI_JVPART01", "JV_PARTNER", affiliateAnnualRevenue: 9_000_000m);

        var result = await _service.CheckSizeEligibilityWithAffiliatesAsync(1, RevenueNaics);

        result.AffiliateCount.Should().Be(2);
        result.CombinedRevenue.Should().Be(27m, "10 + 8 + 9 = 27");
        result.AffiliatedEligible.Should().BeTrue();
        result.IncludedAffiliates.Select(a => a.Uei)
            .Should().BeEquivalentTo(new[] { "UEI_SISTER01", "UEI_JVPART01" });
    }

    // =======================================================================
    // Combined = SUM (not MAX) — employees "E"
    // =======================================================================

    [Fact]
    public async Task Employees_OrgPlusIncludedAffiliate_CombinesAsSum_NotMax()
    {
        // Org 1,000 employees (small). Affiliate 900. Each <= 1,500 cap (MAX would be "small"),
        // but SUM 1,900 > 1,500 => NOT small. No /1,000,000 conversion for headcount.
        SeedOrganization(employeeCount: 1000);
        SeedSizeStandard(EmployeeNaics, "E", EmployeeThreshold);
        SeedLink(1, "UEI_SISTER01", "SISTER_SUBSIDIARY", affiliateEmployeeCount: 900);

        var result = await _service.CheckSizeEligibilityWithAffiliatesAsync(1, EmployeeNaics);

        result.SizeType.Should().Be("E");
        result.CombinedEmployees.Should().Be(1900m, "headcount must be SUM (1000 + 900), not MAX (1000)");
        result.CombinedRevenue.Should().BeNull("revenue is not used for an 'E' standard");
        result.StandaloneEligible.Should().BeTrue("1,000 alone is under the 1,500 cap");
        result.AffiliatedEligible.Should().BeFalse("combined 1,900 exceeds the 1,500 cap");
        result.AffiliateCount.Should().Be(1);
        result.IncludedAffiliates.Single().ContributedAmount.Should().Be(900m);
    }

    [Fact]
    public async Task Employees_CombinedUnderThreshold_IsEligible()
    {
        SeedOrganization(employeeCount: 600);
        SeedSizeStandard(EmployeeNaics, "E", EmployeeThreshold);
        SeedLink(1, "UEI_SISTER01", "SISTER_SUBSIDIARY", affiliateEmployeeCount: 400);

        var result = await _service.CheckSizeEligibilityWithAffiliatesAsync(1, EmployeeNaics);

        result.CombinedEmployees.Should().Be(1000m, "600 + 400 = 1,000");
        result.AffiliatedEligible.Should().BeTrue("1,000 is under the 1,500 cap");
        result.FlippedToOtherThanSmall.Should().BeFalse();
    }

    // =======================================================================
    // Inclusion set: SELF (via org figures), SISTER_SUBSIDIARY, JV_PARTNER
    // =======================================================================

    [Fact]
    public async Task SelfLink_NotReportedAsAffiliate_AndDoesNotDoubleCount()
    {
        // SELF carries the org's OWN figures (sourced from the organization row). It must NOT
        // appear as an included/excluded affiliate and must NOT contribute a second time.
        // Any affiliate figures stashed on the SELF link must be ignored.
        SeedOrganization(annualRevenue: 20_000_000m);
        SeedSizeStandard(RevenueNaics, "M", RevenueThresholdMillions);
        SeedLink(1, "UEI_SELF0001", "SELF", affiliateAnnualRevenue: 999_000_000m);

        var result = await _service.CheckSizeEligibilityWithAffiliatesAsync(1, RevenueNaics);

        result.AffiliateCount.Should().Be(0, "SELF is not an affiliate contribution");
        result.IncludedAffiliates.Should().BeEmpty();
        result.ExcludedAffiliates.Should().BeEmpty();
        result.MissingAffiliateData.Should().BeEmpty();
        result.CombinedRevenue.Should().Be(20m, "only the org's own $20M counts; the SELF link's amount is ignored");
        result.AffiliatedEligible.Should().BeTrue();
    }

    [Fact]
    public async Task SisterSubsidiary_IsIncludedInRollUp()
    {
        SeedOrganization(annualRevenue: 5_000_000m);
        SeedSizeStandard(RevenueNaics, "M", RevenueThresholdMillions);
        SeedLink(1, "UEI_SISTER01", "SISTER_SUBSIDIARY", affiliateAnnualRevenue: 4_000_000m);

        var result = await _service.CheckSizeEligibilityWithAffiliatesAsync(1, RevenueNaics);

        result.AffiliateCount.Should().Be(1);
        result.IncludedAffiliates.Single().Relationship.Should().Be("SISTER_SUBSIDIARY");
        result.CombinedRevenue.Should().Be(9m, "5 + 4 = 9");
    }

    [Fact]
    public async Task JvPartner_NotApproved_IsIncludedInRollUp()
    {
        SeedOrganization(annualRevenue: 5_000_000m);
        SeedSizeStandard(RevenueNaics, "M", RevenueThresholdMillions);
        SeedLink(1, "UEI_JVPART01", "JV_PARTNER", affiliateAnnualRevenue: 6_000_000m, mpaApproved: "N");

        var result = await _service.CheckSizeEligibilityWithAffiliatesAsync(1, RevenueNaics);

        result.AffiliateCount.Should().Be(1);
        result.IncludedAffiliates.Single().Relationship.Should().Be("JV_PARTNER");
        result.ExcludedAffiliates.Should().BeEmpty();
        result.CombinedRevenue.Should().Be(11m, "5 + 6 = 11");
    }

    [Fact]
    public async Task UnrecognizedRelationship_IsSilentlySkipped()
    {
        // A relationship outside { SELF, SISTER_SUBSIDIARY, JV_PARTNER, TEAMING } is not an
        // affiliation-bearing type: not summed, not included, not excluded.
        SeedOrganization(annualRevenue: 10_000_000m);
        SeedSizeStandard(RevenueNaics, "M", RevenueThresholdMillions);
        SeedLink(1, "UEI_MYSTERY1", "PARENT", affiliateAnnualRevenue: 99_000_000m);

        var result = await _service.CheckSizeEligibilityWithAffiliatesAsync(1, RevenueNaics);

        result.AffiliateCount.Should().Be(0);
        result.IncludedAffiliates.Should().BeEmpty();
        result.ExcludedAffiliates.Should().BeEmpty();
        result.MissingAffiliateData.Should().BeEmpty();
        result.CombinedRevenue.Should().Be(10m, "the unrecognized link contributes nothing");
        result.AffiliatedEligible.Should().BeTrue();
    }

    // =======================================================================
    // TEAMING is excluded (does NOT create affiliation under 121.103)
    // =======================================================================

    [Fact]
    public async Task Teaming_IsExcluded_WithReasonTeaming_AndNotSummed()
    {
        // Org 20M alone (small). A TEAMING "partner" at 100M must NOT be summed; if it were,
        // the combined would flip to not-small. Teaming lands in excludedAffiliates / reason TEAMING.
        SeedOrganization(annualRevenue: 20_000_000m);
        SeedSizeStandard(RevenueNaics, "M", RevenueThresholdMillions);
        SeedLink(1, "UEI_TEAMING1", "TEAMING", affiliateAnnualRevenue: 100_000_000m);

        var result = await _service.CheckSizeEligibilityWithAffiliatesAsync(1, RevenueNaics);

        result.AffiliateCount.Should().Be(0, "teaming partners do not count toward size");
        result.IncludedAffiliates.Should().BeEmpty();
        result.ExcludedAffiliates.Should().ContainSingle();
        var excluded = result.ExcludedAffiliates.Single();
        excluded.Uei.Should().Be("UEI_TEAMING1");
        excluded.Relationship.Should().Be("TEAMING");
        excluded.Reason.Should().Be("TEAMING");
        result.MissingAffiliateData.Should().BeEmpty("excluded links are not reported as missing data");
        result.CombinedRevenue.Should().Be(20m, "only the org's $20M counts; teaming partner is excluded");
        result.AffiliatedEligible.Should().BeTrue();
        result.FlippedToOtherThanSmall.Should().BeFalse();
    }

    // =======================================================================
    // Approved-MPA JV is excluded (criterion 12 — owner's two-JV scenario)
    // =======================================================================

    [Fact]
    public async Task ApprovedMpaJv_IsExcluded_WhileUnflaggedJv_IsSummed()
    {
        // The owner's real scenario: two JV partners. One is an SBA-approved mentor-protégé
        // agreement (mpa_approved = 'Y') — the mentor's size is EXCLUDED (13 CFR 125.9). The
        // other, unflagged JV IS summed.
        //   Org 10M + unflagged JV 8M = 18M counted; approved-MPA JV 90M excluded.
        SeedOrganization(annualRevenue: 10_000_000m);
        SeedSizeStandard(RevenueNaics, "M", RevenueThresholdMillions);
        SeedLink(1, "UEI_MPAJVAPP", "JV_PARTNER", affiliateAnnualRevenue: 90_000_000m, mpaApproved: "Y");
        SeedLink(1, "UEI_JVPLAIN1", "JV_PARTNER", affiliateAnnualRevenue: 8_000_000m, mpaApproved: "N");

        var result = await _service.CheckSizeEligibilityWithAffiliatesAsync(1, RevenueNaics);

        // The approved-MPA partner is excluded with the right reason.
        result.ExcludedAffiliates.Should().ContainSingle();
        var excluded = result.ExcludedAffiliates.Single();
        excluded.Uei.Should().Be("UEI_MPAJVAPP");
        excluded.Relationship.Should().Be("JV_PARTNER");
        excluded.Reason.Should().Be("APPROVED_MPA");

        // The unflagged JV is summed.
        result.AffiliateCount.Should().Be(1);
        result.IncludedAffiliates.Single().Uei.Should().Be("UEI_JVPLAIN1");
        result.CombinedRevenue.Should().Be(18m, "10 + 8; the approved-MPA 90M is excluded");
        result.AffiliatedEligible.Should().BeTrue("18M is under the 41.5M cap once the mentor is excluded");
    }

    [Fact]
    public async Task ApprovedMpa_OnlyAppliesToJvPartner_NotSisterSubsidiary()
    {
        // mpa_approved is a JV concept. A SISTER_SUBSIDIARY flagged 'Y' (data oddity) must still
        // be INCLUDED — the MPA exclusion is gated on JV_PARTNER. This pins the gate condition.
        SeedOrganization(annualRevenue: 5_000_000m);
        SeedSizeStandard(RevenueNaics, "M", RevenueThresholdMillions);
        SeedLink(1, "UEI_SISTER01", "SISTER_SUBSIDIARY", affiliateAnnualRevenue: 7_000_000m, mpaApproved: "Y");

        var result = await _service.CheckSizeEligibilityWithAffiliatesAsync(1, RevenueNaics);

        result.ExcludedAffiliates.Should().BeEmpty("MPA exclusion is JV-only");
        result.AffiliateCount.Should().Be(1);
        result.CombinedRevenue.Should().Be(12m, "5 + 7; sister subsidiary counts regardless of mpa flag");
    }

    [Fact]
    public async Task ApprovedMpaJv_ExcludedCanFlipBackToSmall()
    {
        // Demonstrates the consequence of getting the MPA exclusion right: without exclusion the
        // enterprise would be other-than-small; with it, the org stays small.
        //   Org 30M; approved-MPA JV 40M. If wrongly summed => 70M > 41.5M (not small).
        //   Correctly excluded => 30M <= 41.5M (small), matching standalone.
        SeedOrganization(annualRevenue: 30_000_000m);
        SeedSizeStandard(RevenueNaics, "M", RevenueThresholdMillions);
        SeedLink(1, "UEI_MPAJVAPP", "JV_PARTNER", affiliateAnnualRevenue: 40_000_000m, mpaApproved: "Y");

        var result = await _service.CheckSizeEligibilityWithAffiliatesAsync(1, RevenueNaics);

        result.CombinedRevenue.Should().Be(30m, "approved-MPA mentor size must be excluded");
        result.AffiliatedEligible.Should().BeTrue();
        result.StandaloneEligible.Should().BeTrue();
        result.FlippedToOtherThanSmall.Should().BeFalse("excluding the mentor keeps the org small");
    }

    // =======================================================================
    // Missing affiliate data => reported as a GAP, NOT treated as zero
    // =======================================================================

    [Fact]
    public async Task Revenue_IncludedAffiliateWithNullRevenue_ReportedAsGap_NotSummedAsZero()
    {
        // The dangerous silent-zero case. Affiliate has NULL revenue for an 'M' standard.
        // It must: (a) be reported in MissingAffiliateData, (b) appear in IncludedAffiliates with
        // ContributedAmount == null, and (c) NOT be summed as 0. The combined total reflects only
        // the org plus affiliates that DO have data, and the Reason flags it as a lower bound.
        SeedOrganization(annualRevenue: 20_000_000m);
        SeedSizeStandard(RevenueNaics, "M", RevenueThresholdMillions);
        SeedLink(1, "UEI_NODATA01", "SISTER_SUBSIDIARY", affiliateAnnualRevenue: null);

        var result = await _service.CheckSizeEligibilityWithAffiliatesAsync(1, RevenueNaics);

        result.AffiliateCount.Should().Be(1, "the affiliate is still part of the affiliation set");
        result.MissingAffiliateData.Should().ContainSingle().Which.Should().Be("UEI_NODATA01");
        var included = result.IncludedAffiliates.Single();
        included.Uei.Should().Be("UEI_NODATA01");
        included.ContributedAmount.Should().BeNull("a missing figure is a gap, not zero");
        // Combined reflects only the org's $20M; the missing affiliate is NOT added as 0.
        result.CombinedRevenue.Should().Be(20m);
        result.Reason.Should().Contain("lower bound", "the determination must warn that the total is incomplete");
    }

    [Fact]
    public async Task Employees_IncludedAffiliateWithNullCount_ReportedAsGap_NotSummedAsZero()
    {
        SeedOrganization(employeeCount: 800);
        SeedSizeStandard(EmployeeNaics, "E", EmployeeThreshold);
        SeedLink(1, "UEI_NODATA01", "JV_PARTNER", affiliateEmployeeCount: null);

        var result = await _service.CheckSizeEligibilityWithAffiliatesAsync(1, EmployeeNaics);

        result.AffiliateCount.Should().Be(1);
        result.MissingAffiliateData.Should().ContainSingle().Which.Should().Be("UEI_NODATA01");
        result.IncludedAffiliates.Single().ContributedAmount.Should().BeNull();
        result.CombinedEmployees.Should().Be(800m, "missing headcount must not be summed as 0");
        result.Reason.Should().Contain("lower bound");
    }

    [Fact]
    public async Task MissingAffiliateData_OnlyCountsTheMissingOnes_NotDataBearingPeers()
    {
        // Mixed: one affiliate with data, one without. Only the data-less one is a gap; the other
        // is summed normally.
        SeedOrganization(annualRevenue: 10_000_000m);
        SeedSizeStandard(RevenueNaics, "M", RevenueThresholdMillions);
        SeedLink(1, "UEI_HASDATA1", "SISTER_SUBSIDIARY", affiliateAnnualRevenue: 6_000_000m);
        SeedLink(1, "UEI_NODATA01", "JV_PARTNER", affiliateAnnualRevenue: null);

        var result = await _service.CheckSizeEligibilityWithAffiliatesAsync(1, RevenueNaics);

        result.AffiliateCount.Should().Be(2);
        result.MissingAffiliateData.Should().ContainSingle().Which.Should().Be("UEI_NODATA01");
        result.CombinedRevenue.Should().Be(16m, "10 (org) + 6 (data-bearing affiliate); null affiliate not added");
    }

    // =======================================================================
    // flippedToOtherThanSmall semantics
    // =======================================================================

    [Fact]
    public async Task Flipped_StandaloneSmall_CombinedOtherThanSmall_IsTrue()
    {
        // The dangerous case the flag exists for.
        SeedOrganization(annualRevenue: 20_000_000m);
        SeedSizeStandard(RevenueNaics, "M", RevenueThresholdMillions);
        SeedLink(1, "UEI_SISTER01", "SISTER_SUBSIDIARY", affiliateAnnualRevenue: 30_000_000m);

        var result = await _service.CheckSizeEligibilityWithAffiliatesAsync(1, RevenueNaics);

        result.StandaloneEligible.Should().BeTrue();
        result.AffiliatedEligible.Should().BeFalse();
        result.FlippedToOtherThanSmall.Should().BeTrue("small alone but other-than-small once affiliates roll in");
    }

    [Fact]
    public async Task Flipped_BothSmall_IsFalse()
    {
        SeedOrganization(annualRevenue: 10_000_000m);
        SeedSizeStandard(RevenueNaics, "M", RevenueThresholdMillions);
        SeedLink(1, "UEI_SISTER01", "SISTER_SUBSIDIARY", affiliateAnnualRevenue: 5_000_000m);

        var result = await _service.CheckSizeEligibilityWithAffiliatesAsync(1, RevenueNaics);

        result.StandaloneEligible.Should().BeTrue();
        result.AffiliatedEligible.Should().BeTrue();
        result.FlippedToOtherThanSmall.Should().BeFalse();
    }

    [Fact]
    public async Task Flipped_BothOtherThanSmall_IsFalse()
    {
        // Standalone already over the cap, so there is nothing to "flip" from.
        SeedOrganization(annualRevenue: 50_000_000m);
        SeedSizeStandard(RevenueNaics, "M", RevenueThresholdMillions);
        SeedLink(1, "UEI_SISTER01", "SISTER_SUBSIDIARY", affiliateAnnualRevenue: 10_000_000m);

        var result = await _service.CheckSizeEligibilityWithAffiliatesAsync(1, RevenueNaics);

        result.StandaloneEligible.Should().BeFalse("$50M alone already exceeds $41.5M");
        result.AffiliatedEligible.Should().BeFalse("$60M combined also exceeds it");
        result.FlippedToOtherThanSmall.Should().BeFalse("not a flip: it was never small standalone");
    }

    [Fact]
    public async Task Flipped_AtExactThreshold_IsEligible_NotFlipped()
    {
        // Boundary: combined exactly equals the cap. The comparison is "<=", so equal is SMALL.
        // Org 21.5M + affiliate 20M = 41.5M == cap.
        SeedOrganization(annualRevenue: 21_500_000m);
        SeedSizeStandard(RevenueNaics, "M", RevenueThresholdMillions);
        SeedLink(1, "UEI_SISTER01", "SISTER_SUBSIDIARY", affiliateAnnualRevenue: 20_000_000m);

        var result = await _service.CheckSizeEligibilityWithAffiliatesAsync(1, RevenueNaics);

        result.CombinedRevenue.Should().Be(41.5m);
        result.AffiliatedEligible.Should().BeTrue("combined exactly at the cap is still small (<=)");
        result.FlippedToOtherThanSmall.Should().BeFalse();
    }

    // =======================================================================
    // Additive — Phase 129 standalone engine result is unchanged
    // =======================================================================

    [Fact]
    public async Task Additive_StandaloneEligible_MatchesPhase129Engine_Revenue()
    {
        // The affiliated method must report the SAME standalone verdict as the standalone engine
        // (CheckSizeEligibilityAsync) for the same org + NAICS.
        SeedOrganization(annualRevenue: 30_000_000m);
        SeedSizeStandard(RevenueNaics, "M", RevenueThresholdMillions);
        SeedLink(1, "UEI_SISTER01", "SISTER_SUBSIDIARY", affiliateAnnualRevenue: 25_000_000m);

        var standalone = await _service.CheckSizeEligibilityAsync(1, RevenueNaics);
        var affiliated = await _service.CheckSizeEligibilityWithAffiliatesAsync(1, RevenueNaics);

        affiliated.StandaloneEligible.Should().Be(standalone.Eligible,
            "the standalone verdict must be unchanged by the affiliation roll-up");
        standalone.Eligible.Should().BeTrue("$30M alone is under the $41.5M cap");
        // Sanity: the combined verdict differs from standalone in this scenario.
        affiliated.AffiliatedEligible.Should().BeFalse("$55M combined exceeds the cap");
    }

    [Fact]
    public async Task Additive_StandaloneEligible_MatchesPhase129Engine_Employees()
    {
        SeedOrganization(employeeCount: 1200);
        SeedSizeStandard(EmployeeNaics, "E", EmployeeThreshold);
        SeedLink(1, "UEI_SISTER01", "SISTER_SUBSIDIARY", affiliateEmployeeCount: 500);

        var standalone = await _service.CheckSizeEligibilityAsync(1, EmployeeNaics);
        var affiliated = await _service.CheckSizeEligibilityWithAffiliatesAsync(1, EmployeeNaics);

        affiliated.StandaloneEligible.Should().Be(standalone.Eligible);
        standalone.Eligible.Should().BeTrue("1,200 alone is under the 1,500 cap");
        affiliated.AffiliatedEligible.Should().BeFalse("1,700 combined exceeds the cap");
    }

    [Fact]
    public async Task Additive_NoAffiliates_AffiliatedEqualsStandalone()
    {
        // With no affiliate links, the combined total is the org alone, so both verdicts agree.
        SeedOrganization(annualRevenue: 30_000_000m);
        SeedSizeStandard(RevenueNaics, "M", RevenueThresholdMillions);

        var result = await _service.CheckSizeEligibilityWithAffiliatesAsync(1, RevenueNaics);

        result.AffiliateCount.Should().Be(0);
        result.StandaloneEligible.Should().BeTrue();
        result.AffiliatedEligible.Should().BeTrue();
        result.CombinedRevenue.Should().Be(30m);
        result.FlippedToOtherThanSmall.Should().BeFalse();
    }

    // =======================================================================
    // Inactive links are ignored
    // =======================================================================

    [Fact]
    public async Task InactiveLink_IsIgnored_NotSummed_NotReported()
    {
        // An inactive (is_active='N') affiliate must be invisible to the roll-up entirely:
        // not summed, not included, not excluded, not a gap. A huge inactive figure would
        // flip the result if it leaked in.
        SeedOrganization(annualRevenue: 20_000_000m);
        SeedSizeStandard(RevenueNaics, "M", RevenueThresholdMillions);
        SeedLink(1, "UEI_INACTIVE", "SISTER_SUBSIDIARY", active: false, affiliateAnnualRevenue: 500_000_000m);

        var result = await _service.CheckSizeEligibilityWithAffiliatesAsync(1, RevenueNaics);

        result.AffiliateCount.Should().Be(0);
        result.IncludedAffiliates.Should().BeEmpty();
        result.ExcludedAffiliates.Should().BeEmpty();
        result.MissingAffiliateData.Should().BeEmpty();
        result.CombinedRevenue.Should().Be(20m, "inactive affiliate contributes nothing");
        result.AffiliatedEligible.Should().BeTrue();
    }

    [Fact]
    public async Task InactiveTeamingLink_IsIgnored_NotEvenExcluded()
    {
        // Inactive links are filtered at the query level (is_active='Y'), so an inactive TEAMING
        // link should not even appear in excludedAffiliates.
        SeedOrganization(annualRevenue: 20_000_000m);
        SeedSizeStandard(RevenueNaics, "M", RevenueThresholdMillions);
        SeedLink(1, "UEI_INACTTEAM", "TEAMING", active: false, affiliateAnnualRevenue: 100_000_000m);

        var result = await _service.CheckSizeEligibilityWithAffiliatesAsync(1, RevenueNaics);

        result.ExcludedAffiliates.Should().BeEmpty("inactive links are filtered before exclusion logic");
        result.CombinedRevenue.Should().Be(20m);
    }

    // =======================================================================
    // Org missing its own figure for the needed size_type
    // =======================================================================

    [Fact]
    public async Task Revenue_OrgRevenueNull_AffiliatedEligibleIsNull_AndCombinedNull()
    {
        // Without the org's own receipts the combined total is undeterminable. The method returns
        // AffiliatedEligible = null, CombinedRevenue = null, and an explanatory reason — it does
        // NOT default the org to 0.
        SeedOrganization(annualRevenue: null);
        SeedSizeStandard(RevenueNaics, "M", RevenueThresholdMillions);
        SeedLink(1, "UEI_SISTER01", "SISTER_SUBSIDIARY", affiliateAnnualRevenue: 10_000_000m);

        var result = await _service.CheckSizeEligibilityWithAffiliatesAsync(1, RevenueNaics);

        result.AffiliatedEligible.Should().BeNull("org receipts unknown => combined undeterminable");
        result.CombinedRevenue.Should().BeNull();
        result.StandaloneEligible.Should().BeNull("standalone is also undeterminable without revenue");
        result.FlippedToOtherThanSmall.Should().BeFalse("cannot flip when nothing is determinable");
        result.Reason.Should().Contain("annual revenue not set");
    }

    [Fact]
    public async Task Employees_OrgEmployeeCountNull_AffiliatedEligibleIsNull_AndCombinedNull()
    {
        SeedOrganization(employeeCount: null);
        SeedSizeStandard(EmployeeNaics, "E", EmployeeThreshold);
        SeedLink(1, "UEI_SISTER01", "SISTER_SUBSIDIARY", affiliateEmployeeCount: 100);

        var result = await _service.CheckSizeEligibilityWithAffiliatesAsync(1, EmployeeNaics);

        result.AffiliatedEligible.Should().BeNull();
        result.CombinedEmployees.Should().BeNull();
        result.StandaloneEligible.Should().BeNull();
        result.Reason.Should().Contain("employee count not set");
    }

    // =======================================================================
    // Standard / org lookup edge cases
    // =======================================================================

    [Fact]
    public async Task OrgNotFound_ReturnsOrganizationNotFound()
    {
        SeedSizeStandard(RevenueNaics, "M", RevenueThresholdMillions);

        var result = await _service.CheckSizeEligibilityWithAffiliatesAsync(999, RevenueNaics);

        result.StandaloneEligible.Should().BeNull();
        result.AffiliatedEligible.Should().BeNull();
        result.Reason.Should().Be("Organization not found.");
    }

    [Fact]
    public async Task NoSizeStandardOnFile_CannotRollUp()
    {
        SeedOrganization(annualRevenue: 20_000_000m);
        // No ref_sba_size_standard row for this NAICS.

        var result = await _service.CheckSizeEligibilityWithAffiliatesAsync(1, RevenueNaics);

        result.SizeType.Should().BeNull();
        result.Threshold.Should().BeNull();
        result.AffiliatedEligible.Should().BeNull();
        result.Reason.Should().Contain("No SBA size standard on file");
    }

    [Fact]
    public async Task UnrecognizedSizeType_CannotRollUp()
    {
        // size_type other than 'M' or 'E' (e.g. legacy 'R') cannot be rolled up.
        SeedOrganization(annualRevenue: 20_000_000m);
        SeedSizeStandard(RevenueNaics, "R", 10m);

        var result = await _service.CheckSizeEligibilityWithAffiliatesAsync(1, RevenueNaics);

        result.AffiliatedEligible.Should().BeNull();
        result.Reason.Should().Contain("Unrecognized SBA size type");
    }

    [Fact]
    public async Task SizeStandardZero_TreatedAsNoUsableStandard()
    {
        // A zero/blank threshold is not a usable cap; the method must refuse to roll up rather
        // than divide-by-zero or declare everything "not small".
        SeedOrganization(annualRevenue: 20_000_000m);
        SeedSizeStandard(RevenueNaics, "M", 0m);

        var result = await _service.CheckSizeEligibilityWithAffiliatesAsync(1, RevenueNaics);

        result.AffiliatedEligible.Should().BeNull();
        result.Reason.Should().Contain("No SBA size standard on file");
    }

    [Fact]
    public async Task MultipleStandards_LatestEffectiveDateWins()
    {
        // ref_sba_size_standard can hold multiple rows per NAICS; the roll-up must use the most
        // recent effective_date. Older row caps at 10M, newer at 41.5M; org+affiliate = 30M.
        SeedOrganization(annualRevenue: 20_000_000m);
        SeedSizeStandard(RevenueNaics, "M", 10m, effectiveDate: new DateOnly(2020, 1, 1));
        SeedSizeStandard(RevenueNaics, "M", RevenueThresholdMillions, effectiveDate: new DateOnly(2024, 1, 1));
        SeedLink(1, "UEI_SISTER01", "SISTER_SUBSIDIARY", affiliateAnnualRevenue: 10_000_000m);

        var result = await _service.CheckSizeEligibilityWithAffiliatesAsync(1, RevenueNaics);

        result.Threshold.Should().Be(RevenueThresholdMillions, "the latest effective standard must win");
        result.CombinedRevenue.Should().Be(30m);
        result.AffiliatedEligible.Should().BeTrue("30M is under the current 41.5M cap (would fail the old 10M cap)");
    }

    // =======================================================================
    // Multi-tenant isolation — only THIS org's links are rolled up
    // =======================================================================

    [Fact]
    public async Task OnlyTargetOrgLinks_AreRolledUp_OtherOrgsIgnored()
    {
        // Another org's affiliate links must never bleed into this org's determination.
        SeedOrganization(orgId: 1, annualRevenue: 20_000_000m);
        SeedOrganization(orgId: 2, annualRevenue: 5_000_000m);
        SeedSizeStandard(RevenueNaics, "M", RevenueThresholdMillions);
        SeedLink(1, "UEI_OWN00001", "SISTER_SUBSIDIARY", affiliateAnnualRevenue: 5_000_000m);
        SeedLink(2, "UEI_OTHER001", "SISTER_SUBSIDIARY", affiliateAnnualRevenue: 100_000_000m);

        var result = await _service.CheckSizeEligibilityWithAffiliatesAsync(1, RevenueNaics);

        result.AffiliateCount.Should().Be(1, "only org 1's link counts");
        result.IncludedAffiliates.Single().Uei.Should().Be("UEI_OWN00001");
        result.CombinedRevenue.Should().Be(25m, "20 + 5; org 2's 100M affiliate is irrelevant");
    }
}
