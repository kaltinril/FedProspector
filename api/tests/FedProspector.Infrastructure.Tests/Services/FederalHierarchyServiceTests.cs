using FedProspector.Core.DTOs;
using FedProspector.Core.DTOs.FederalHierarchy;
using FedProspector.Core.Models;
using FedProspector.Infrastructure.Data;
using FedProspector.Infrastructure.Services;
using FluentAssertions;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging.Abstractions;

namespace FedProspector.Infrastructure.Tests.Services;

public class FederalHierarchyServiceTests : IDisposable
{
    private readonly FedProspectorDbContext _context;
    private readonly FederalHierarchyService _service;

    public FederalHierarchyServiceTests()
    {
        var options = new DbContextOptionsBuilder<FedProspectorDbContext>()
            .UseInMemoryDatabase(databaseName: Guid.NewGuid().ToString())
            .Options;

        _context = new FedProspectorDbContext(options);
        _service = new FederalHierarchyService(_context, NullLogger<FederalHierarchyService>.Instance);
    }

    public void Dispose()
    {
        _context.Dispose();
    }

    // --- Seed helpers ---

    private FederalOrganization SeedOrg(int id, string name, string type = "Department",
        string status = "Active", int? level = 1, int? parentOrgId = null,
        string? agencyCode = null, string? cgac = null, string? description = null,
        string? oldfpdsOfficeCode = null)
    {
        var org = new FederalOrganization
        {
            FhOrgId = id,
            FhOrgName = name,
            FhOrgType = type,
            Status = status,
            Level = level,
            ParentOrgId = parentOrgId,
            AgencyCode = agencyCode,
            Cgac = cgac,
            Description = description,
            OldfpdsOfficeCode = oldfpdsOfficeCode,
            CreatedDate = new DateOnly(2024, 1, 1),
            LastModifiedDate = new DateOnly(2024, 6, 15),
            LastLoadedAt = new DateTime(2024, 6, 15, 10, 0, 0, DateTimeKind.Utc)
        };
        _context.FederalOrganizations.Add(org);
        _context.SaveChanges();
        return org;
    }

    private Opportunity SeedOpportunity(string noticeId, string? title = null,
        string? departmentName = null, string? subTier = null, string? office = null,
        DateOnly? postedDate = null, string? type = null, string? setAsideCode = null,
        string? active = null, string? naicsCode = null)
    {
        var opp = new Opportunity
        {
            NoticeId = noticeId,
            Title = title ?? $"Opportunity {noticeId}",
            DepartmentName = departmentName,
            SubTier = subTier,
            Office = office,
            PostedDate = postedDate ?? new DateOnly(2024, 6, 1),
            Type = type,
            SetAsideCode = setAsideCode,
            Active = active ?? "Yes",
            NaicsCode = naicsCode
        };
        _context.Opportunities.Add(opp);
        _context.SaveChanges();
        return opp;
    }

    private EtlLoadLog SeedLoadLog(string sourceSystem = "fedhier", string status = "completed",
        DateTime? startedAt = null, DateTime? completedAt = null,
        int inserted = 0, int updated = 0, int unchanged = 0)
    {
        var log = new EtlLoadLog
        {
            SourceSystem = sourceSystem,
            LoadType = "full",
            Status = status,
            StartedAt = startedAt ?? new DateTime(2024, 6, 15, 10, 0, 0, DateTimeKind.Utc),
            CompletedAt = completedAt,
            RecordsInserted = inserted,
            RecordsUpdated = updated,
            RecordsUnchanged = unchanged
        };
        _context.EtlLoadLogs.Add(log);
        _context.SaveChanges();
        return log;
    }

    /// <summary>
    /// Seeds a 3-level hierarchy: Department -> SubTier -> Office
    /// </summary>
    private (FederalOrganization dept, FederalOrganization subTier, FederalOrganization office) SeedHierarchy()
    {
        var dept = SeedOrg(100, "Department of Defense", "Department", "Active", 1, agencyCode: "DOD", cgac: "097");
        var subTier = SeedOrg(200, "Army", "Sub-Tier", "Active", 2, parentOrgId: 100, agencyCode: "ARMY");
        var office = SeedOrg(300, "Army Contracting Command", "Office", "Active", 3, parentOrgId: 200);
        return (dept, subTier, office);
    }

    // ===========================
    // SearchAsync tests
    // ===========================

    [Fact(Skip = "Requires relational database — EF.Functions.Like not supported by InMemory provider")]
    public async Task SearchAsync_KeywordFilter_MatchesByName()
    {
        SeedOrg(1, "Department of Defense", agencyCode: "DOD");
        SeedOrg(2, "Department of Energy", agencyCode: "DOE");

        var result = await _service.SearchAsync(new FederalOrgSearchRequestDto { Keyword = "Defense" });

        result.TotalCount.Should().Be(1);
        result.Items.Should().ContainSingle(o => o.FhOrgName == "Department of Defense");
    }

    [Fact]
    public async Task SearchAsync_FilterByType_ReturnsMatchingType()
    {
        SeedOrg(1, "Dept A", type: "Department");
        SeedOrg(2, "Sub-Tier B", type: "Sub-Tier", level: 2, parentOrgId: 1);

        var result = await _service.SearchAsync(new FederalOrgSearchRequestDto { FhOrgType = "Sub-Tier" });

        result.TotalCount.Should().Be(1);
        result.Items.Should().ContainSingle(o => o.FhOrgType == "Sub-Tier");
    }

    [Fact]
    public async Task SearchAsync_FilterByStatus_ReturnsMatchingStatus()
    {
        SeedOrg(1, "Active Dept", status: "Active");
        SeedOrg(2, "Inactive Dept", status: "Inactive");

        var result = await _service.SearchAsync(new FederalOrgSearchRequestDto { Status = "Active" });

        result.TotalCount.Should().Be(1);
        result.Items.Should().ContainSingle(o => o.FhOrgName == "Active Dept");
    }

    [Fact]
    public async Task SearchAsync_FilterByLevel_ReturnsMatchingLevel()
    {
        SeedOrg(1, "Dept", level: 1);
        SeedOrg(2, "Sub-Tier", level: 2, parentOrgId: 1);
        SeedOrg(3, "Office", level: 3, parentOrgId: 2);

        var result = await _service.SearchAsync(new FederalOrgSearchRequestDto { Level = 2 });

        result.TotalCount.Should().Be(1);
        result.Items.Should().ContainSingle(o => o.FhOrgName == "Sub-Tier");
    }

    [Fact]
    public async Task SearchAsync_Pagination_RespectsPageAndPageSize()
    {
        for (int i = 1; i <= 10; i++)
            SeedOrg(i, $"Org {i:D2}");

        var result = await _service.SearchAsync(new FederalOrgSearchRequestDto { Page = 2, PageSize = 3 });

        result.TotalCount.Should().Be(10);
        result.Items.Should().HaveCount(3);
        result.Page.Should().Be(2);
        result.PageSize.Should().Be(3);
    }

    [Fact]
    public async Task SearchAsync_NoMatches_ReturnsEmptyResult()
    {
        SeedOrg(1, "Department of Defense");

        var result = await _service.SearchAsync(new FederalOrgSearchRequestDto { FhOrgType = "NonExistentType" });

        result.TotalCount.Should().Be(0);
        result.Items.Should().BeEmpty();
    }

    [Fact]
    public async Task SearchAsync_FilterByAgencyCode_ReturnsMatch()
    {
        SeedOrg(1, "Dept A", agencyCode: "DOD");
        SeedOrg(2, "Dept B", agencyCode: "DOE");

        var result = await _service.SearchAsync(new FederalOrgSearchRequestDto { AgencyCode = "DOD" });

        result.TotalCount.Should().Be(1);
        result.Items.Should().ContainSingle(o => o.AgencyCode == "DOD");
    }

    [Fact]
    public async Task SearchAsync_FilterByCgac_ReturnsMatch()
    {
        SeedOrg(1, "Dept A", cgac: "097");
        SeedOrg(2, "Dept B", cgac: "089");

        var result = await _service.SearchAsync(new FederalOrgSearchRequestDto { Cgac = "097" });

        result.TotalCount.Should().Be(1);
        result.Items.Should().ContainSingle(o => o.Cgac == "097");
    }

    [Fact]
    public async Task SearchAsync_FilterByParentOrgId_ReturnsChildren()
    {
        SeedOrg(1, "Dept");
        SeedOrg(2, "Child A", type: "Sub-Tier", level: 2, parentOrgId: 1);
        SeedOrg(3, "Child B", type: "Sub-Tier", level: 2, parentOrgId: 1);
        SeedOrg(4, "Other", type: "Sub-Tier", level: 2, parentOrgId: 99);

        var result = await _service.SearchAsync(new FederalOrgSearchRequestDto { ParentOrgId = 1 });

        result.TotalCount.Should().Be(2);
        result.Items.Select(o => o.FhOrgName).Should().BeEquivalentTo("Child A", "Child B");
    }

    [Fact]
    public async Task SearchAsync_SortByName_ReturnsSorted()
    {
        SeedOrg(1, "Zebra Dept");
        SeedOrg(2, "Alpha Dept");
        SeedOrg(3, "Middle Dept");

        var result = await _service.SearchAsync(new FederalOrgSearchRequestDto { SortBy = "name" });

        result.Items.Select(o => o.FhOrgName).Should().BeInAscendingOrder();
    }

    [Fact]
    public async Task SearchAsync_SortByNameDescending_ReturnsSortedDesc()
    {
        SeedOrg(1, "Zebra Dept");
        SeedOrg(2, "Alpha Dept");
        SeedOrg(3, "Middle Dept");

        var result = await _service.SearchAsync(new FederalOrgSearchRequestDto
        {
            SortBy = "name",
            SortDescending = true
        });

        result.Items.Select(o => o.FhOrgName).Should().BeInDescendingOrder();
    }

    // ===========================
    // GetDetailAsync tests
    // ===========================

    [Fact]
    public async Task GetDetailAsync_ExistingOrg_ReturnsDetailWithParentChain()
    {
        var (dept, subTier, office) = SeedHierarchy();

        var result = await _service.GetDetailAsync(300);

        result.Should().NotBeNull();
        result!.FhOrgId.Should().Be(300);
        result.FhOrgName.Should().Be("Army Contracting Command");
        result.FhOrgType.Should().Be("Office");
        result.Level.Should().Be(3);
        result.ParentOrgId.Should().Be(200);
        result.Description.Should().BeNull();
        result.ChildCount.Should().Be(0);
        result.ParentChain.Should().HaveCount(2);
    }

    [Fact]
    public async Task GetDetailAsync_ExistingOrg_ParentChainOrderedRootFirst()
    {
        SeedHierarchy();

        var result = await _service.GetDetailAsync(300);

        result.Should().NotBeNull();
        result!.ParentChain.Should().HaveCount(2);
        // Root (Department) should be first, immediate parent (Sub-Tier) second
        result.ParentChain[0].FhOrgId.Should().Be(100);
        result.ParentChain[0].FhOrgName.Should().Be("Department of Defense");
        result.ParentChain[1].FhOrgId.Should().Be(200);
        result.ParentChain[1].FhOrgName.Should().Be("Army");
    }

    [Fact]
    public async Task GetDetailAsync_NonExistentOrg_ReturnsNull()
    {
        var result = await _service.GetDetailAsync(999);

        result.Should().BeNull();
    }

    [Fact]
    public async Task GetDetailAsync_RootOrg_HasEmptyParentChain()
    {
        SeedOrg(1, "Department of Defense", level: 1);

        var result = await _service.GetDetailAsync(1);

        result.Should().NotBeNull();
        result!.ParentChain.Should().BeEmpty();
    }

    [Fact]
    public async Task GetDetailAsync_OrgWithChildren_ReturnsCorrectChildCount()
    {
        SeedOrg(1, "Department", level: 1);
        SeedOrg(2, "Sub-Tier A", type: "Sub-Tier", level: 2, parentOrgId: 1);
        SeedOrg(3, "Sub-Tier B", type: "Sub-Tier", level: 2, parentOrgId: 1);
        SeedOrg(4, "Sub-Tier C", type: "Sub-Tier", level: 2, parentOrgId: 1);

        var result = await _service.GetDetailAsync(1);

        result.Should().NotBeNull();
        result!.ChildCount.Should().Be(3);
    }

    [Fact]
    public async Task GetDetailAsync_ReturnsAllDetailFields()
    {
        SeedOrg(1, "Test Dept", description: "A test department",
            oldfpdsOfficeCode: "OLDFPDS1", agencyCode: "TEST", cgac: "001");

        var result = await _service.GetDetailAsync(1);

        result.Should().NotBeNull();
        result!.Description.Should().Be("A test department");
        result.OldfpdsOfficeCode.Should().Be("OLDFPDS1");
        result.AgencyCode.Should().Be("TEST");
        result.Cgac.Should().Be("001");
        result.CreatedDate.Should().Be(new DateOnly(2024, 1, 1));
        result.LastModifiedDate.Should().Be(new DateOnly(2024, 6, 15));
        result.LastLoadedAt.Should().NotBeNull();
    }

    // ===========================
    // GetChildrenAsync tests
    // ===========================

    [Fact]
    public async Task GetChildrenAsync_ReturnsDirectChildrenOnly()
    {
        SeedHierarchy();

        var result = await _service.GetChildrenAsync(100);

        result.Should().HaveCount(1);
        result[0].FhOrgId.Should().Be(200);
        result[0].FhOrgName.Should().Be("Army");
    }

    [Fact]
    public async Task GetChildrenAsync_FilterByStatus_ReturnsMatchingOnly()
    {
        SeedOrg(1, "Department", level: 1);
        SeedOrg(2, "Active Child", type: "Sub-Tier", status: "Active", level: 2, parentOrgId: 1);
        SeedOrg(3, "Inactive Child", type: "Sub-Tier", status: "Inactive", level: 2, parentOrgId: 1);

        var result = await _service.GetChildrenAsync(1, status: "Active");

        result.Should().HaveCount(1);
        result[0].FhOrgName.Should().Be("Active Child");
    }

    [Fact]
    public async Task GetChildrenAsync_StatusAll_ReturnsAllChildren()
    {
        SeedOrg(1, "Department", level: 1);
        SeedOrg(2, "Active Child", type: "Sub-Tier", status: "Active", level: 2, parentOrgId: 1);
        SeedOrg(3, "Inactive Child", type: "Sub-Tier", status: "Inactive", level: 2, parentOrgId: 1);

        var result = await _service.GetChildrenAsync(1, status: "All");

        result.Should().HaveCount(2);
    }

    [Fact(Skip = "Requires relational database — EF.Functions.Like not supported by InMemory provider")]
    public async Task GetChildrenAsync_FilterByKeyword_MatchesChildName()
    {
        SeedOrg(1, "Department", level: 1);
        SeedOrg(2, "Army", type: "Sub-Tier", level: 2, parentOrgId: 1);
        SeedOrg(3, "Navy", type: "Sub-Tier", level: 2, parentOrgId: 1);

        var result = await _service.GetChildrenAsync(1, keyword: "Army");

        result.Should().HaveCount(1);
        result[0].FhOrgName.Should().Be("Army");
    }

    [Fact]
    public async Task GetChildrenAsync_NoChildren_ReturnsEmpty()
    {
        SeedOrg(1, "Leaf Node", type: "Office", level: 3, parentOrgId: 99);

        var result = await _service.GetChildrenAsync(1);

        result.Should().BeEmpty();
    }

    [Fact]
    public async Task GetChildrenAsync_PopulatesChildCounts()
    {
        SeedOrg(1, "Department", level: 1);
        SeedOrg(2, "Sub-Tier With Kids", type: "Sub-Tier", level: 2, parentOrgId: 1);
        SeedOrg(3, "Sub-Tier No Kids", type: "Sub-Tier", level: 2, parentOrgId: 1);
        SeedOrg(4, "Office A", type: "Office", level: 3, parentOrgId: 2);
        SeedOrg(5, "Office B", type: "Office", level: 3, parentOrgId: 2);

        var result = await _service.GetChildrenAsync(1);

        result.Should().HaveCount(2);
        var withKids = result.First(c => c.FhOrgId == 2);
        var noKids = result.First(c => c.FhOrgId == 3);
        withKids.ChildCount.Should().Be(2);
        noKids.ChildCount.Should().Be(0);
    }

    [Fact]
    public async Task GetChildrenAsync_OrderedByName()
    {
        SeedOrg(1, "Department", level: 1);
        SeedOrg(2, "Zebra Agency", type: "Sub-Tier", level: 2, parentOrgId: 1);
        SeedOrg(3, "Alpha Agency", type: "Sub-Tier", level: 2, parentOrgId: 1);
        SeedOrg(4, "Middle Agency", type: "Sub-Tier", level: 2, parentOrgId: 1);

        var result = await _service.GetChildrenAsync(1);

        result.Select(c => c.FhOrgName).Should().BeInAscendingOrder();
    }

    // ===========================
    // GetTreeAsync tests
    // ===========================

    [Fact]
    public async Task GetTreeAsync_NoKeyword_ReturnsActiveLevel1Orgs()
    {
        SeedOrg(1, "Dept of Defense", level: 1, status: "Active");
        SeedOrg(2, "Dept of Energy", level: 1, status: "Active");
        SeedOrg(3, "Inactive Dept", level: 1, status: "Inactive");

        var result = await _service.GetTreeAsync();

        result.Should().HaveCount(2);
        result.Select(d => d.FhOrgName).Should().NotContain("Inactive Dept");
    }

    [Fact]
    public async Task GetTreeAsync_NoKeyword_IncludesChildAndDescendantCounts()
    {
        SeedOrg(1, "Dept of Defense", level: 1, status: "Active");
        SeedOrg(10, "Army", type: "Sub-Tier", level: 2, parentOrgId: 1);
        SeedOrg(11, "Navy", type: "Sub-Tier", level: 2, parentOrgId: 1);
        SeedOrg(100, "Army Contracting", type: "Office", level: 3, parentOrgId: 10);
        SeedOrg(101, "Army Logistics", type: "Office", level: 3, parentOrgId: 10);
        SeedOrg(110, "Naval Supply", type: "Office", level: 3, parentOrgId: 11);

        var result = await _service.GetTreeAsync();

        result.Should().HaveCount(1);
        var dod = result[0];
        dod.FhOrgId.Should().Be(1);
        dod.ChildCount.Should().Be(2); // Army + Navy
        dod.DescendantCount.Should().Be(5); // 2 sub-tiers + 3 offices
    }

    [Fact]
    public async Task GetTreeAsync_NoKeyword_OrderedByName()
    {
        SeedOrg(1, "Dept of Zebra", level: 1, status: "Active");
        SeedOrg(2, "Dept of Alpha", level: 1, status: "Active");
        SeedOrg(3, "Dept of Middle", level: 1, status: "Active");

        var result = await _service.GetTreeAsync();

        result.Select(d => d.FhOrgName).Should().BeInAscendingOrder();
    }

    [Fact(Skip = "Requires relational database — EF.Functions.Like not supported by InMemory provider")]
    public async Task GetTreeAsync_WithKeyword_FiltersToDepartmentsContainingMatch()
    {
        SeedOrg(1, "Dept of Defense", level: 1, status: "Active");
        SeedOrg(2, "Dept of Energy", level: 1, status: "Active");
        SeedOrg(10, "Army", type: "Sub-Tier", level: 2, parentOrgId: 1);

        var result = await _service.GetTreeAsync(keyword: "Army");

        result.Should().ContainSingle(d => d.FhOrgName == "Dept of Defense");
        result.Should().NotContain(d => d.FhOrgName == "Dept of Energy");
    }

    [Fact]
    public async Task GetTreeAsync_NoDepartments_ReturnsEmpty()
    {
        // Only non-level-1 orgs, or inactive level-1 orgs
        SeedOrg(1, "Sub-Tier Only", type: "Sub-Tier", level: 2, status: "Active");

        var result = await _service.GetTreeAsync();

        result.Should().BeEmpty();
    }

    // ===========================
    // GetOpportunitiesAsync tests
    // ===========================

    [Fact]
    public async Task GetOpportunitiesAsync_MatchesByDepartmentName()
    {
        SeedOrg(1, "Dept of Defense", level: 1);
        SeedOpportunity("OPP-1", departmentName: "Dept of Defense");
        SeedOpportunity("OPP-2", departmentName: "Dept of Energy");

        var result = await _service.GetOpportunitiesAsync(1, new PagedRequest());

        result.TotalCount.Should().Be(1);
        result.Items.Should().ContainSingle(o => o.NoticeId == "OPP-1");
    }

    [Fact]
    public async Task GetOpportunitiesAsync_MatchesByDescendantNames()
    {
        SeedOrg(1, "Dept of Defense", level: 1);
        SeedOrg(10, "Army", type: "Sub-Tier", level: 2, parentOrgId: 1);
        SeedOrg(100, "Army Contracting Command", type: "Office", level: 3, parentOrgId: 10);

        SeedOpportunity("OPP-DEPT", departmentName: "Dept of Defense");
        SeedOpportunity("OPP-SUB", subTier: "Army");
        SeedOpportunity("OPP-OFFICE", office: "Army Contracting Command");
        SeedOpportunity("OPP-OTHER", departmentName: "Dept of Energy");

        var result = await _service.GetOpportunitiesAsync(1, new PagedRequest());

        result.TotalCount.Should().Be(3);
        result.Items.Select(o => o.NoticeId).Should().BeEquivalentTo("OPP-DEPT", "OPP-SUB", "OPP-OFFICE");
    }

    [Fact]
    public async Task GetOpportunitiesAsync_Pagination_RespectsPageAndPageSize()
    {
        SeedOrg(1, "Dept of Defense", level: 1);
        for (int i = 1; i <= 10; i++)
            SeedOpportunity($"OPP-{i:D2}", departmentName: "Dept of Defense",
                postedDate: new DateOnly(2024, 6, i));

        var result = await _service.GetOpportunitiesAsync(1, new PagedRequest { Page = 2, PageSize = 3 });

        result.TotalCount.Should().Be(10);
        result.Items.Should().HaveCount(3);
        result.Page.Should().Be(2);
    }

    [Fact]
    public async Task GetOpportunitiesAsync_FilterByActive_ReturnsMatchingOnly()
    {
        SeedOrg(1, "Dept of Defense", level: 1);
        SeedOpportunity("OPP-1", departmentName: "Dept of Defense", active: "Yes");
        SeedOpportunity("OPP-2", departmentName: "Dept of Defense", active: "No");

        var result = await _service.GetOpportunitiesAsync(1, new PagedRequest(), active: "Yes");

        result.TotalCount.Should().Be(1);
        result.Items.Should().ContainSingle(o => o.NoticeId == "OPP-1");
    }

    [Fact]
    public async Task GetOpportunitiesAsync_FilterByType_ReturnsMatchingOnly()
    {
        SeedOrg(1, "Dept of Defense", level: 1);
        SeedOpportunity("OPP-1", departmentName: "Dept of Defense", type: "Solicitation");
        SeedOpportunity("OPP-2", departmentName: "Dept of Defense", type: "Presolicitation");

        var result = await _service.GetOpportunitiesAsync(1, new PagedRequest(), type: "Solicitation");

        result.TotalCount.Should().Be(1);
        result.Items.Should().ContainSingle(o => o.NoticeId == "OPP-1");
    }

    [Fact]
    public async Task GetOpportunitiesAsync_FilterBySetAsideCode_ReturnsMatchingOnly()
    {
        SeedOrg(1, "Dept of Defense", level: 1);
        SeedOpportunity("OPP-1", departmentName: "Dept of Defense", setAsideCode: "WOSB");
        SeedOpportunity("OPP-2", departmentName: "Dept of Defense", setAsideCode: "SBA");

        var result = await _service.GetOpportunitiesAsync(1, new PagedRequest(), setAsideCode: "WOSB");

        result.TotalCount.Should().Be(1);
        result.Items.Should().ContainSingle(o => o.NoticeId == "OPP-1");
    }

    [Fact]
    public async Task GetOpportunitiesAsync_NonExistentOrg_ReturnsEmpty()
    {
        SeedOpportunity("OPP-1", departmentName: "Dept of Defense");

        var result = await _service.GetOpportunitiesAsync(999, new PagedRequest());

        result.TotalCount.Should().Be(0);
        result.Items.Should().BeEmpty();
    }

    [Fact]
    public async Task GetOpportunitiesAsync_NoMatchingOpportunities_ReturnsEmpty()
    {
        SeedOrg(1, "Dept of Defense", level: 1);
        SeedOpportunity("OPP-1", departmentName: "Dept of Energy");

        var result = await _service.GetOpportunitiesAsync(1, new PagedRequest());

        result.TotalCount.Should().Be(0);
        result.Items.Should().BeEmpty();
    }

    [Fact]
    public async Task GetOpportunitiesAsync_OrderedByPostedDateDescending()
    {
        SeedOrg(1, "Dept of Defense", level: 1);
        SeedOpportunity("OPP-OLD", departmentName: "Dept of Defense", postedDate: new DateOnly(2024, 1, 1));
        SeedOpportunity("OPP-NEW", departmentName: "Dept of Defense", postedDate: new DateOnly(2024, 6, 15));
        SeedOpportunity("OPP-MID", departmentName: "Dept of Defense", postedDate: new DateOnly(2024, 3, 10));

        var result = await _service.GetOpportunitiesAsync(1, new PagedRequest());

        result.Items.Select(o => o.NoticeId).Should().ContainInOrder("OPP-NEW", "OPP-MID", "OPP-OLD");
    }

    [Fact]
    public async Task GetOpportunitiesAsync_MultipleFilters_AppliedTogether()
    {
        SeedOrg(1, "Dept of Defense", level: 1);
        SeedOpportunity("OPP-1", departmentName: "Dept of Defense", active: "Yes", type: "Solicitation", setAsideCode: "WOSB");
        SeedOpportunity("OPP-2", departmentName: "Dept of Defense", active: "Yes", type: "Solicitation", setAsideCode: "SBA");
        SeedOpportunity("OPP-3", departmentName: "Dept of Defense", active: "No", type: "Solicitation", setAsideCode: "WOSB");

        var result = await _service.GetOpportunitiesAsync(1, new PagedRequest(),
            active: "Yes", type: "Solicitation", setAsideCode: "WOSB");

        result.TotalCount.Should().Be(1);
        result.Items.Should().ContainSingle(o => o.NoticeId == "OPP-1");
    }

    // ===========================
    // GetRefreshStatusAsync tests
    // ===========================

    [Fact]
    public async Task GetRefreshStatusAsync_WithCompletedLoad_ReturnsStatus()
    {
        var completedAt = new DateTime(2024, 6, 15, 11, 0, 0, DateTimeKind.Utc);
        SeedLoadLog("fedhier", "completed",
            startedAt: new DateTime(2024, 6, 15, 10, 0, 0, DateTimeKind.Utc),
            completedAt: completedAt,
            inserted: 100, updated: 50, unchanged: 850);

        // Also seed some orgs for level counts
        SeedOrg(1, "Dept", level: 1);
        SeedOrg(2, "Sub-Tier", type: "Sub-Tier", level: 2, parentOrgId: 1);
        SeedOrg(3, "Office", type: "Office", level: 3, parentOrgId: 2);

        var result = await _service.GetRefreshStatusAsync();

        result.IsRunning.Should().BeFalse();
        result.LastRefreshAt.Should().Be(completedAt);
        result.LastRefreshRecordCount.Should().Be(1000); // 100 + 50 + 850
        result.LevelsLoaded.Should().HaveCount(3);
        result.LevelsLoaded.Should().Contain(l => l.Level == 1 && l.Count == 1);
        result.LevelsLoaded.Should().Contain(l => l.Level == 2 && l.Count == 1);
        result.LevelsLoaded.Should().Contain(l => l.Level == 3 && l.Count == 1);
    }

    [Fact]
    public async Task GetRefreshStatusAsync_WithRunningLoad_IsRunningTrue()
    {
        SeedLoadLog("fedhier", "running",
            startedAt: new DateTime(2024, 6, 15, 10, 0, 0, DateTimeKind.Utc));

        var result = await _service.GetRefreshStatusAsync();

        result.IsRunning.Should().BeTrue();
        result.LastRefreshAt.Should().NotBeNull(); // Falls back to StartedAt
    }

    [Fact]
    public async Task GetRefreshStatusAsync_NoLogs_ReturnsDefaultStatus()
    {
        var result = await _service.GetRefreshStatusAsync();

        result.IsRunning.Should().BeFalse();
        result.LastRefreshAt.Should().BeNull();
        result.LastRefreshRecordCount.Should().BeNull();
        result.LevelsLoaded.Should().BeEmpty();
        result.JobId.Should().BeNull();
    }

    [Fact]
    public async Task GetRefreshStatusAsync_MultipleLoads_ReturnsLatest()
    {
        SeedLoadLog("fedhier", "completed",
            startedAt: new DateTime(2024, 6, 10, 10, 0, 0, DateTimeKind.Utc),
            completedAt: new DateTime(2024, 6, 10, 11, 0, 0, DateTimeKind.Utc),
            inserted: 10);
        SeedLoadLog("fedhier", "completed",
            startedAt: new DateTime(2024, 6, 15, 10, 0, 0, DateTimeKind.Utc),
            completedAt: new DateTime(2024, 6, 15, 11, 0, 0, DateTimeKind.Utc),
            inserted: 100, updated: 50);

        var result = await _service.GetRefreshStatusAsync();

        result.LastRefreshRecordCount.Should().Be(150); // 100 + 50 + 0 from latest
        result.LastRefreshAt.Should().Be(new DateTime(2024, 6, 15, 11, 0, 0, DateTimeKind.Utc));
    }

    [Fact]
    public async Task GetRefreshStatusAsync_IgnoresNonFedhierLogs()
    {
        SeedLoadLog("opportunity", "completed",
            startedAt: new DateTime(2024, 6, 15, 10, 0, 0, DateTimeKind.Utc),
            completedAt: new DateTime(2024, 6, 15, 11, 0, 0, DateTimeKind.Utc),
            inserted: 500);

        var result = await _service.GetRefreshStatusAsync();

        result.IsRunning.Should().BeFalse();
        result.LastRefreshAt.Should().BeNull();
        result.LastRefreshRecordCount.Should().BeNull();
    }

    [Fact]
    public async Task GetRefreshStatusAsync_ReturnsJobId()
    {
        var log = SeedLoadLog("fedhier", "completed",
            startedAt: new DateTime(2024, 6, 15, 10, 0, 0, DateTimeKind.Utc),
            completedAt: new DateTime(2024, 6, 15, 11, 0, 0, DateTimeKind.Utc));

        var result = await _service.GetRefreshStatusAsync();

        result.JobId.Should().Be(log.LoadId);
    }

    [Fact]
    public async Task GetRefreshStatusAsync_LevelCountsOrderedByLevel()
    {
        SeedOrg(1, "Office", type: "Office", level: 3);
        SeedOrg(2, "Dept", level: 1);
        SeedOrg(3, "Sub-Tier", type: "Sub-Tier", level: 2);

        var result = await _service.GetRefreshStatusAsync();

        result.LevelsLoaded.Select(l => l.Level).Should().BeInAscendingOrder();
    }
}
