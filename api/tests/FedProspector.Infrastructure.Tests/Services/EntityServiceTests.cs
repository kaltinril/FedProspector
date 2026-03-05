using FedProspector.Core.DTOs.Entities;
using FedProspector.Core.Models;
using FedProspector.Infrastructure.Data;
using FedProspector.Infrastructure.Services;
using FluentAssertions;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging.Abstractions;

namespace FedProspector.Infrastructure.Tests.Services;

public class EntityServiceTests : IDisposable
{
    private readonly FedProspectorDbContext _context;
    private readonly EntityService _service;

    public EntityServiceTests()
    {
        var options = new DbContextOptionsBuilder<FedProspectorDbContext>()
            .UseInMemoryDatabase(databaseName: Guid.NewGuid().ToString())
            .Options;

        _context = new FedProspectorDbContext(options);
        _service = new EntityService(_context, NullLogger<EntityService>.Instance);
    }

    public void Dispose()
    {
        _context.Dispose();
    }

    private void SeedEntities(int count = 3)
    {
        for (int i = 1; i <= count; i++)
        {
            _context.Entities.Add(new Entity
            {
                UeiSam = $"UEI{i:D9}",
                LegalBusinessName = $"Company {i}",
                RegistrationStatus = "A",
                PrimaryNaics = $"5415{i:D2}",
                EntityStructureCode = "2L"
            });
        }
        _context.SaveChanges();
    }

    private void SeedEntityWithBusinessType(string uei, string businessName, string businessTypeCode)
    {
        _context.Entities.Add(new Entity
        {
            UeiSam = uei,
            LegalBusinessName = businessName,
            RegistrationStatus = "A",
            PrimaryNaics = "541512"
        });
        _context.EntityBusinessTypes.Add(new EntityBusinessType
        {
            UeiSam = uei,
            BusinessTypeCode = businessTypeCode
        });
        _context.SaveChanges();
    }

    private void SeedEntityWithAddress(string uei, string businessName, string state)
    {
        _context.Entities.Add(new Entity
        {
            UeiSam = uei,
            LegalBusinessName = businessName,
            RegistrationStatus = "A"
        });
        _context.EntityAddresses.Add(new EntityAddress
        {
            UeiSam = uei,
            AddressType = "physical",
            StateOrProvince = state,
            City = "TestCity"
        });
        _context.SaveChanges();
    }

    // --- SearchAsync tests ---

    [Fact]
    public async Task SearchAsync_ReturnsPagedResults()
    {
        SeedEntities(5);

        var request = new EntitySearchRequest { Page = 1, PageSize = 3 };
        var result = await _service.SearchAsync(request);

        result.TotalCount.Should().Be(5);
        result.Items.Should().HaveCount(3);
        result.Page.Should().Be(1);
        result.PageSize.Should().Be(3);
    }

    [Fact]
    public async Task SearchAsync_FiltersByUei()
    {
        SeedEntities(3);

        var request = new EntitySearchRequest { Uei = "UEI000000002" };
        var result = await _service.SearchAsync(request);

        result.TotalCount.Should().Be(1);
        result.Items.Should().ContainSingle()
            .Which.UeiSam.Should().Be("UEI000000002");
    }

    [Fact]
    public async Task SearchAsync_FiltersByBusinessType()
    {
        SeedEntityWithBusinessType("UEI000000001", "WOSB Corp", "2X");
        SeedEntityWithBusinessType("UEI000000002", "Regular Corp", "A2");

        var request = new EntitySearchRequest { BusinessType = "2X" };
        var result = await _service.SearchAsync(request);

        result.TotalCount.Should().Be(1);
        result.Items.Should().ContainSingle()
            .Which.LegalBusinessName.Should().Be("WOSB Corp");
    }

    // --- GetDetailAsync tests ---

    [Fact]
    public async Task GetDetailAsync_ExistingUei_ReturnsDetail()
    {
        _context.Entities.Add(new Entity
        {
            UeiSam = "UEI000000001",
            LegalBusinessName = "Test Corp",
            RegistrationStatus = "A",
            PrimaryNaics = "541512",
            ExclusionStatusFlag = "N"
        });
        _context.EntityAddresses.Add(new EntityAddress
        {
            UeiSam = "UEI000000001",
            AddressType = "physical",
            City = "Washington",
            StateOrProvince = "DC"
        });
        _context.EntityNaicsCodes.Add(new EntityNaics
        {
            UeiSam = "UEI000000001",
            NaicsCode = "541512",
            IsPrimary = "Y"
        });
        _context.SaveChanges();

        var result = await _service.GetDetailAsync("UEI000000001");

        result.Should().NotBeNull();
        result!.UeiSam.Should().Be("UEI000000001");
        result.LegalBusinessName.Should().Be("Test Corp");
        result.Addresses.Should().HaveCount(1);
        result.NaicsCodes.Should().HaveCount(1);
    }

    [Fact]
    public async Task GetDetailAsync_NonexistentUei_ReturnsNull()
    {
        var result = await _service.GetDetailAsync("NONEXISTENT");

        result.Should().BeNull();
    }

    // --- GetCompetitorProfileAsync tests ---
    // Note: CompetitorAnalysisView is configured as a keyless entity type
    // mapped to a database view. The in-memory provider does not support
    // Add() on keyless entities, so this test verifies a null return for
    // a non-existent UEI (the positive path requires a real database).

    [Fact]
    public async Task GetCompetitorProfileAsync_NonexistentUei_ReturnsNull()
    {
        var result = await _service.GetCompetitorProfileAsync("NONEXISTENT");

        result.Should().BeNull();
    }

    // --- CheckExclusionAsync tests ---

    [Fact]
    public async Task CheckExclusionAsync_NoExclusion_ReturnsClean()
    {
        _context.Entities.Add(new Entity
        {
            UeiSam = "UEI000000001",
            LegalBusinessName = "Clean Corp"
        });
        _context.SaveChanges();

        var result = await _service.CheckExclusionAsync("UEI000000001");

        result.Uei.Should().Be("UEI000000001");
        result.EntityName.Should().Be("Clean Corp");
        result.IsExcluded.Should().BeFalse();
        result.ActiveExclusions.Should().BeEmpty();
    }
}
