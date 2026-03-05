using System.Text.Json;
using AutoMapper;
using FedProspector.Core.DTOs.SavedSearches;
using FedProspector.Core.Interfaces;
using FedProspector.Core.Mapping;
using FedProspector.Core.Models;
using FedProspector.Infrastructure.Data;
using FedProspector.Infrastructure.Services;
using FluentAssertions;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Logging.Abstractions;
using Moq;

namespace FedProspector.Infrastructure.Tests.Services;

public class SavedSearchServiceTests : IDisposable
{
    private readonly FedProspectorDbContext _context;
    private readonly SavedSearchService _service;
    private readonly Mock<INotificationService> _notificationMock;
    private readonly IMapper _mapper;

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        WriteIndented = false
    };

    public SavedSearchServiceTests()
    {
        var options = new DbContextOptionsBuilder<FedProspectorDbContext>()
            .UseInMemoryDatabase(databaseName: Guid.NewGuid().ToString())
            .Options;

        _context = new FedProspectorDbContext(options);

        var expression = new MapperConfigurationExpression();
        expression.AddProfile<MappingProfile>();
        var mapperConfig = new MapperConfiguration(expression, NullLoggerFactory.Instance);
        _mapper = mapperConfig.CreateMapper();

        _notificationMock = new Mock<INotificationService>();

        _service = new SavedSearchService(
            _context,
            _mapper,
            _notificationMock.Object,
            NullLogger<SavedSearchService>.Instance);
    }

    public void Dispose()
    {
        _context.Dispose();
    }

    private SavedSearch SeedSavedSearch(
        int userId = 1,
        int organizationId = 1,
        string searchName = "Test Search",
        string? description = null,
        SavedSearchFilterCriteria? criteria = null,
        string isActive = "Y",
        string notificationEnabled = "N",
        DateTime? lastRunAt = null)
    {
        var filterCriteria = criteria ?? new SavedSearchFilterCriteria();

        var search = new SavedSearch
        {
            OrganizationId = organizationId,
            UserId = userId,
            SearchName = searchName,
            Description = description,
            FilterCriteria = JsonSerializer.Serialize(filterCriteria, JsonOptions),
            IsActive = isActive,
            NotificationEnabled = notificationEnabled,
            LastRunAt = lastRunAt,
            CreatedAt = DateTime.UtcNow,
            UpdatedAt = DateTime.UtcNow
        };

        _context.SavedSearches.Add(search);
        _context.SaveChanges();

        return search;
    }

    private void SeedOpportunities(params Opportunity[] opportunities)
    {
        _context.Opportunities.AddRange(opportunities);
        _context.SaveChanges();
    }

    // --- CreateAsync Tests ---

    [Fact]
    public async Task CreateAsync_ValidRequest_CreatesSavedSearch()
    {
        var request = new CreateSavedSearchRequest
        {
            SearchName = "WOSB Opportunities",
            Description = "Find WOSB set-aside contracts",
            FilterCriteria = new SavedSearchFilterCriteria
            {
                SetAsideCodes = ["WOSB", "EDWOSB"],
                OpenOnly = true
            },
            NotificationEnabled = true
        };

        var result = await _service.CreateAsync(userId: 1, organizationId: 1, request);

        result.Should().NotBeNull();
        result.SearchName.Should().Be("WOSB Opportunities");
        result.Description.Should().Be("Find WOSB set-aside contracts");
        result.NotificationEnabled.Should().Be("Y");
        result.IsActive.Should().Be("Y");
        result.SearchId.Should().BeGreaterThan(0);

        // Verify persisted in DB
        var saved = await _context.SavedSearches.FindAsync(result.SearchId);
        saved.Should().NotBeNull();
        saved!.UserId.Should().Be(1);
        saved.OrganizationId.Should().Be(1);
    }

    [Fact]
    public async Task CreateAsync_SerializesFilterCriteria()
    {
        var request = new CreateSavedSearchRequest
        {
            SearchName = "NAICS Filter",
            FilterCriteria = new SavedSearchFilterCriteria
            {
                NaicsCodes = ["541512", "541511"],
                MinAwardAmount = 100_000m,
                MaxAwardAmount = 5_000_000m
            }
        };

        var result = await _service.CreateAsync(userId: 1, organizationId: 1, request);

        var saved = await _context.SavedSearches.FindAsync(result.SearchId);
        saved.Should().NotBeNull();

        var deserialized = JsonSerializer.Deserialize<SavedSearchFilterCriteria>(saved!.FilterCriteria, JsonOptions);
        deserialized.Should().NotBeNull();
        deserialized!.NaicsCodes.Should().Contain("541512");
        deserialized.MinAwardAmount.Should().Be(100_000m);
    }

    // --- ListAsync Tests ---

    [Fact]
    public async Task ListAsync_ReturnsUserSearches()
    {
        SeedSavedSearch(userId: 1, searchName: "Search A");
        SeedSavedSearch(userId: 1, searchName: "Search B");
        SeedSavedSearch(userId: 2, searchName: "Other User Search");

        var results = (await _service.ListAsync(userId: 1)).ToList();

        results.Should().HaveCount(2);
        results.Select(s => s.SearchName).Should().Contain("Search A");
        results.Select(s => s.SearchName).Should().Contain("Search B");
        results.Select(s => s.SearchName).Should().NotContain("Other User Search");
    }

    [Fact]
    public async Task ListAsync_ExcludesInactiveSearches()
    {
        SeedSavedSearch(userId: 1, searchName: "Active Search", isActive: "Y");
        SeedSavedSearch(userId: 1, searchName: "Deleted Search", isActive: "N");

        var results = (await _service.ListAsync(userId: 1)).ToList();

        results.Should().HaveCount(1);
        results[0].SearchName.Should().Be("Active Search");
    }

    [Fact]
    public async Task ListAsync_ReturnsOrderedByName()
    {
        SeedSavedSearch(userId: 1, searchName: "Zebra Search");
        SeedSavedSearch(userId: 1, searchName: "Alpha Search");
        SeedSavedSearch(userId: 1, searchName: "Middle Search");

        var results = (await _service.ListAsync(userId: 1)).ToList();

        results.Should().HaveCount(3);
        results[0].SearchName.Should().Be("Alpha Search");
        results[1].SearchName.Should().Be("Middle Search");
        results[2].SearchName.Should().Be("Zebra Search");
    }

    [Fact]
    public async Task ListAsync_NoSearches_ReturnsEmpty()
    {
        var results = (await _service.ListAsync(userId: 999)).ToList();

        results.Should().BeEmpty();
    }

    // --- GetByIdAsync Tests ---

    [Fact]
    public async Task GetByIdAsync_ExistingSearch_ReturnsSearch()
    {
        var search = SeedSavedSearch(userId: 1, searchName: "My Search", description: "Test desc");

        var result = await _service.GetByIdAsync(search.SearchId, userId: 1);

        result.Should().NotBeNull();
        result!.SearchId.Should().Be(search.SearchId);
        result.SearchName.Should().Be("My Search");
        result.Description.Should().Be("Test desc");
    }

    [Fact]
    public async Task GetByIdAsync_WrongUser_ReturnsNull()
    {
        var search = SeedSavedSearch(userId: 1, searchName: "User 1 Search");

        var result = await _service.GetByIdAsync(search.SearchId, userId: 2);

        result.Should().BeNull();
    }

    [Fact]
    public async Task GetByIdAsync_InactiveSearch_ReturnsNull()
    {
        var search = SeedSavedSearch(userId: 1, searchName: "Deleted", isActive: "N");

        var result = await _service.GetByIdAsync(search.SearchId, userId: 1);

        result.Should().BeNull();
    }

    [Fact]
    public async Task GetByIdAsync_NonexistentId_ReturnsNull()
    {
        var result = await _service.GetByIdAsync(searchId: 999, userId: 1);

        result.Should().BeNull();
    }

    // --- DeleteAsync Tests ---

    [Fact]
    public async Task DeleteAsync_OwnSearch_ReturnsTrue()
    {
        var search = SeedSavedSearch(userId: 1, searchName: "To Delete");

        var result = await _service.DeleteAsync(userId: 1, searchId: search.SearchId);

        result.Should().BeTrue();

        // Verify soft delete (IsActive = "N")
        var deleted = await _context.SavedSearches.FindAsync(search.SearchId);
        deleted!.IsActive.Should().Be("N");
    }

    [Fact]
    public async Task DeleteAsync_OtherUserSearch_ReturnsFalse()
    {
        var search = SeedSavedSearch(userId: 1, searchName: "Not Yours");

        var result = await _service.DeleteAsync(userId: 2, searchId: search.SearchId);

        result.Should().BeFalse();

        // Verify not deleted
        var notDeleted = await _context.SavedSearches.FindAsync(search.SearchId);
        notDeleted!.IsActive.Should().Be("Y");
    }

    [Fact]
    public async Task DeleteAsync_NonexistentSearch_ReturnsFalse()
    {
        var result = await _service.DeleteAsync(userId: 1, searchId: 999);

        result.Should().BeFalse();
    }

    // --- UpdateAsync Tests ---

    [Fact]
    public async Task UpdateAsync_ValidRequest_UpdatesSearch()
    {
        var search = SeedSavedSearch(userId: 1, searchName: "Old Name", description: "Old Desc");

        var request = new UpdateSavedSearchRequest
        {
            Name = "New Name",
            Description = "New Desc"
        };

        var result = await _service.UpdateAsync(userId: 1, searchId: search.SearchId, request);

        result.Should().NotBeNull();
        result!.SearchName.Should().Be("New Name");
        result.Description.Should().Be("New Desc");
    }

    [Fact]
    public async Task UpdateAsync_PartialUpdate_OnlyChangesProvidedFields()
    {
        var search = SeedSavedSearch(userId: 1, searchName: "Keep Name", description: "Old Desc");

        var request = new UpdateSavedSearchRequest
        {
            Description = "Updated Desc"
            // Name is null, should not change
        };

        var result = await _service.UpdateAsync(userId: 1, searchId: search.SearchId, request);

        result.Should().NotBeNull();
        result!.SearchName.Should().Be("Keep Name");
        result.Description.Should().Be("Updated Desc");
    }

    [Fact]
    public async Task UpdateAsync_UpdatesNotificationEnabled()
    {
        var search = SeedSavedSearch(userId: 1, notificationEnabled: "N");

        var request = new UpdateSavedSearchRequest
        {
            NotificationsEnabled = true
        };

        var result = await _service.UpdateAsync(userId: 1, searchId: search.SearchId, request);

        result.Should().NotBeNull();
        result!.NotificationEnabled.Should().Be("Y");
    }

    [Fact]
    public async Task UpdateAsync_UpdatesFilterCriteria()
    {
        var search = SeedSavedSearch(userId: 1);

        var newCriteria = new SavedSearchFilterCriteria
        {
            States = ["VA", "MD", "DC"],
            OpenOnly = true
        };

        var request = new UpdateSavedSearchRequest
        {
            FilterCriteria = newCriteria
        };

        var result = await _service.UpdateAsync(userId: 1, searchId: search.SearchId, request);

        result.Should().NotBeNull();

        var updated = await _context.SavedSearches.FindAsync(search.SearchId);
        var deserialized = JsonSerializer.Deserialize<SavedSearchFilterCriteria>(updated!.FilterCriteria, JsonOptions);
        deserialized!.States.Should().Contain("VA");
        deserialized.States.Should().HaveCount(3);
    }

    [Fact]
    public async Task UpdateAsync_WrongUser_ReturnsNull()
    {
        var search = SeedSavedSearch(userId: 1, searchName: "Not Yours");

        var request = new UpdateSavedSearchRequest { Name = "Hijacked" };
        var result = await _service.UpdateAsync(userId: 2, searchId: search.SearchId, request);

        result.Should().BeNull();

        // Verify unchanged
        var unchanged = await _context.SavedSearches.FindAsync(search.SearchId);
        unchanged!.SearchName.Should().Be("Not Yours");
    }

    [Fact]
    public async Task UpdateAsync_InactiveSearch_ReturnsNull()
    {
        var search = SeedSavedSearch(userId: 1, isActive: "N");

        var request = new UpdateSavedSearchRequest { Name = "Revive" };
        var result = await _service.UpdateAsync(userId: 1, searchId: search.SearchId, request);

        result.Should().BeNull();
    }

    [Fact]
    public async Task UpdateAsync_NonexistentSearch_ReturnsNull()
    {
        var request = new UpdateSavedSearchRequest { Name = "Ghost" };
        var result = await _service.UpdateAsync(userId: 1, searchId: 999, request);

        result.Should().BeNull();
    }

    // --- RunAsync Tests ---

    [Fact]
    public async Task RunAsync_ValidSearch_ReturnsResults()
    {
        var criteria = new SavedSearchFilterCriteria
        {
            SetAsideCodes = ["WOSB"],
            OpenOnly = false
        };
        var search = SeedSavedSearch(userId: 1, searchName: "WOSB Search", criteria: criteria);

        SeedOpportunities(
            new Opportunity
            {
                NoticeId = "OPP-001",
                Title = "WOSB Contract",
                SetAsideCode = "WOSB",
                Active = "Y",
                ResponseDeadline = DateTime.UtcNow.AddDays(30)
            },
            new Opportunity
            {
                NoticeId = "OPP-002",
                Title = "Full and Open",
                SetAsideCode = "NONE",
                Active = "Y",
                ResponseDeadline = DateTime.UtcNow.AddDays(30)
            }
        );

        var result = await _service.RunAsync(userId: 1, searchId: search.SearchId);

        result.Should().NotBeNull();
        result!.SearchId.Should().Be(search.SearchId);
        result.SearchName.Should().Be("WOSB Search");
        result.TotalCount.Should().Be(1);
        result.Results.Should().HaveCount(1);
        result.Results[0].NoticeId.Should().Be("OPP-001");
    }

    [Fact]
    public async Task RunAsync_WrongUser_ReturnsNull()
    {
        var search = SeedSavedSearch(userId: 1);

        var result = await _service.RunAsync(userId: 2, searchId: search.SearchId);

        result.Should().BeNull();
    }

    [Fact]
    public async Task RunAsync_InactiveSearch_ReturnsNull()
    {
        var search = SeedSavedSearch(userId: 1, isActive: "N");

        var result = await _service.RunAsync(userId: 1, searchId: search.SearchId);

        result.Should().BeNull();
    }

    [Fact]
    public async Task RunAsync_UpdatesLastRunAt()
    {
        var criteria = new SavedSearchFilterCriteria { OpenOnly = false };
        var search = SeedSavedSearch(userId: 1, criteria: criteria);

        var beforeRun = DateTime.UtcNow;
        await _service.RunAsync(userId: 1, searchId: search.SearchId);

        var updated = await _context.SavedSearches.FindAsync(search.SearchId);
        updated!.LastRunAt.Should().NotBeNull();
        updated.LastRunAt.Should().BeOnOrAfter(beforeRun);
    }

    [Fact]
    public async Task RunAsync_NaicsFilter_FiltersCorrectly()
    {
        var criteria = new SavedSearchFilterCriteria
        {
            NaicsCodes = ["541512"],
            OpenOnly = false
        };
        var search = SeedSavedSearch(userId: 1, criteria: criteria);

        SeedOpportunities(
            new Opportunity { NoticeId = "N1", Title = "Match", NaicsCode = "541512" },
            new Opportunity { NoticeId = "N2", Title = "No Match", NaicsCode = "999999" }
        );

        var result = await _service.RunAsync(userId: 1, searchId: search.SearchId);

        result!.TotalCount.Should().Be(1);
        result.Results[0].NoticeId.Should().Be("N1");
    }

    [Fact]
    public async Task RunAsync_StateFilter_FiltersCorrectly()
    {
        var criteria = new SavedSearchFilterCriteria
        {
            States = ["VA", "MD"],
            OpenOnly = false
        };
        var search = SeedSavedSearch(userId: 1, criteria: criteria);

        SeedOpportunities(
            new Opportunity { NoticeId = "N1", Title = "Virginia", PopState = "VA" },
            new Opportunity { NoticeId = "N2", Title = "Maryland", PopState = "MD" },
            new Opportunity { NoticeId = "N3", Title = "California", PopState = "CA" }
        );

        var result = await _service.RunAsync(userId: 1, searchId: search.SearchId);

        result!.TotalCount.Should().Be(2);
        result.Results.Select(r => r.NoticeId).Should().Contain("N1").And.Contain("N2");
    }

    [Fact]
    public async Task RunAsync_AwardAmountFilter_FiltersCorrectly()
    {
        var criteria = new SavedSearchFilterCriteria
        {
            MinAwardAmount = 100_000m,
            MaxAwardAmount = 500_000m,
            OpenOnly = false
        };
        var search = SeedSavedSearch(userId: 1, criteria: criteria);

        SeedOpportunities(
            new Opportunity { NoticeId = "N1", Title = "Too Small", AwardAmount = 50_000m },
            new Opportunity { NoticeId = "N2", Title = "Just Right", AwardAmount = 250_000m },
            new Opportunity { NoticeId = "N3", Title = "Too Large", AwardAmount = 1_000_000m }
        );

        var result = await _service.RunAsync(userId: 1, searchId: search.SearchId);

        result!.TotalCount.Should().Be(1);
        result.Results[0].NoticeId.Should().Be("N2");
    }

    [Fact]
    public async Task RunAsync_NoFilters_ReturnsAllOpportunities()
    {
        var criteria = new SavedSearchFilterCriteria { OpenOnly = false };
        var search = SeedSavedSearch(userId: 1, criteria: criteria);

        SeedOpportunities(
            new Opportunity { NoticeId = "N1", Title = "One" },
            new Opportunity { NoticeId = "N2", Title = "Two" },
            new Opportunity { NoticeId = "N3", Title = "Three" }
        );

        var result = await _service.RunAsync(userId: 1, searchId: search.SearchId);

        result!.TotalCount.Should().Be(3);
    }

    [Fact]
    public async Task RunAsync_LimitsTo200Results()
    {
        var criteria = new SavedSearchFilterCriteria { OpenOnly = false };
        var search = SeedSavedSearch(userId: 1, criteria: criteria);

        var opportunities = Enumerable.Range(1, 210)
            .Select(i => new Opportunity
            {
                NoticeId = $"BULK-{i:D4}",
                Title = $"Opportunity {i}",
                ResponseDeadline = DateTime.UtcNow.AddDays(i)
            })
            .ToArray();
        SeedOpportunities(opportunities);

        var result = await _service.RunAsync(userId: 1, searchId: search.SearchId);

        result!.TotalCount.Should().Be(200);
        result.Results.Should().HaveCount(200);
    }
}
