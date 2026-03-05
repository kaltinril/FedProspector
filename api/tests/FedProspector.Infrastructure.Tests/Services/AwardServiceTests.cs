using FedProspector.Core.DTOs.Awards;
using FedProspector.Core.Models;
using FedProspector.Infrastructure.Data;
using FedProspector.Infrastructure.Services;
using FluentAssertions;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging.Abstractions;

namespace FedProspector.Infrastructure.Tests.Services;

public class AwardServiceTests : IDisposable
{
    private readonly FedProspectorDbContext _context;
    private readonly AwardService _service;

    public AwardServiceTests()
    {
        var options = new DbContextOptionsBuilder<FedProspectorDbContext>()
            .UseInMemoryDatabase(databaseName: Guid.NewGuid().ToString())
            .Options;

        _context = new FedProspectorDbContext(options);
        _service = new AwardService(_context, NullLogger<AwardService>.Instance);
    }

    public void Dispose()
    {
        _context.Dispose();
    }

    // -----------------------------------------------------------------------
    // Seed Helpers
    // -----------------------------------------------------------------------

    private void SeedContract(
        string contractId,
        string modificationNumber = "0",
        string? agencyName = null,
        string? naicsCode = null,
        string? setAsideType = null,
        string? vendorName = null,
        string? vendorUei = null,
        decimal? dollarsObligated = null,
        decimal? baseAndAllOptions = null,
        DateOnly? dateSigned = null,
        string? solicitationNumber = null)
    {
        _context.FpdsContracts.Add(new FpdsContract
        {
            ContractId = contractId,
            ModificationNumber = modificationNumber,
            AgencyName = agencyName ?? "Test Agency",
            NaicsCode = naicsCode,
            SetAsideType = setAsideType,
            VendorName = vendorName ?? "Test Vendor",
            VendorUei = vendorUei,
            DollarsObligated = dollarsObligated,
            BaseAndAllOptions = baseAndAllOptions,
            DateSigned = dateSigned ?? DateOnly.FromDateTime(DateTime.UtcNow),
            SolicitationNumber = solicitationNumber
        });
        _context.SaveChanges();
    }

    private void SeedMultipleContracts(int count, string? agencyName = null, string? naicsCode = null)
    {
        for (int i = 1; i <= count; i++)
        {
            SeedContract(
                $"CONTRACT-{i:D3}",
                agencyName: agencyName,
                naicsCode: naicsCode,
                dateSigned: DateOnly.FromDateTime(DateTime.UtcNow.AddDays(-i)));
        }
    }

    // -----------------------------------------------------------------------
    // SearchAsync Tests
    // -----------------------------------------------------------------------

    [Fact]
    public async Task SearchAsync_ReturnsPagedResults()
    {
        SeedMultipleContracts(5);

        var request = new AwardSearchRequest
        {
            Page = 1,
            PageSize = 3
        };

        var result = await _service.SearchAsync(request);

        result.TotalCount.Should().Be(5);
        result.Items.Count().Should().Be(3);
        result.Page.Should().Be(1);
        result.PageSize.Should().Be(3);
        result.HasNextPage.Should().BeTrue();
    }

    [Fact]
    public async Task SearchAsync_OnlyReturnsBaseAwards()
    {
        // Base award
        SeedContract("CONTRACT-001", modificationNumber: "0");
        // Modification (should be excluded)
        SeedContract("CONTRACT-001", modificationNumber: "1");

        var request = new AwardSearchRequest();

        var result = await _service.SearchAsync(request);

        result.TotalCount.Should().Be(1);
        result.Items.Should().ContainSingle(a => a.ContractId == "CONTRACT-001");
    }

    [Fact]
    public async Task SearchAsync_FiltersByNaics()
    {
        SeedContract("CONTRACT-IT", naicsCode: "541512");
        SeedContract("CONTRACT-CONSTRUCTION", naicsCode: "236220");

        var request = new AwardSearchRequest { Naics = "541512" };

        var result = await _service.SearchAsync(request);

        result.TotalCount.Should().Be(1);
        result.Items.Should().ContainSingle(a => a.ContractId == "CONTRACT-IT");
    }

    [Fact]
    public async Task SearchAsync_FiltersBySetAside()
    {
        SeedContract("CONTRACT-WOSB", setAsideType: "WOSB");
        SeedContract("CONTRACT-FULL", setAsideType: null);

        var request = new AwardSearchRequest { SetAside = "WOSB" };

        var result = await _service.SearchAsync(request);

        result.TotalCount.Should().Be(1);
        result.Items.Should().ContainSingle(a => a.ContractId == "CONTRACT-WOSB");
    }

    [Fact]
    public async Task SearchAsync_FiltersByVendorUei()
    {
        SeedContract("CONTRACT-V1", vendorUei: "UEI000000001");
        SeedContract("CONTRACT-V2", vendorUei: "UEI000000002");

        var request = new AwardSearchRequest { VendorUei = "UEI000000001" };

        var result = await _service.SearchAsync(request);

        result.TotalCount.Should().Be(1);
        result.Items.Should().ContainSingle(a => a.ContractId == "CONTRACT-V1");
    }

    [Fact]
    public async Task SearchAsync_FiltersByValueRange()
    {
        SeedContract("CONTRACT-SMALL", baseAndAllOptions: 50_000m);
        SeedContract("CONTRACT-MEDIUM", baseAndAllOptions: 500_000m);
        SeedContract("CONTRACT-LARGE", baseAndAllOptions: 5_000_000m);

        var request = new AwardSearchRequest
        {
            MinValue = 100_000m,
            MaxValue = 1_000_000m
        };

        var result = await _service.SearchAsync(request);

        result.TotalCount.Should().Be(1);
        result.Items.Should().ContainSingle(a => a.ContractId == "CONTRACT-MEDIUM");
    }

    // -----------------------------------------------------------------------
    // GetDetailAsync Tests
    // -----------------------------------------------------------------------

    [Fact]
    public async Task GetDetailAsync_ExistingContract_ReturnsDetail()
    {
        SeedContract("CONTRACT-001", naicsCode: "541512", vendorName: "Acme Corp",
            vendorUei: "UEI000000001", dollarsObligated: 1_000_000m);

        var result = await _service.GetDetailAsync("CONTRACT-001");

        result.Should().NotBeNull();
        result!.ContractId.Should().Be("CONTRACT-001");
        result.NaicsCode.Should().Be("541512");
        result.VendorName.Should().Be("Acme Corp");
        result.DollarsObligated.Should().Be(1_000_000m);
    }

    [Fact]
    public async Task GetDetailAsync_NonexistentContract_ReturnsNull()
    {
        var result = await _service.GetDetailAsync("NONEXISTENT");

        result.Should().BeNull();
    }

    [Fact]
    public async Task GetDetailAsync_OnlyFindsBaseAward()
    {
        // Only a modification exists, no base award
        SeedContract("CONTRACT-MOD-ONLY", modificationNumber: "1");

        var result = await _service.GetDetailAsync("CONTRACT-MOD-ONLY");

        result.Should().BeNull();
    }

    [Fact]
    public async Task GetDetailAsync_IncludesVendorProfile()
    {
        SeedContract("CONTRACT-001", vendorUei: "UEI000000001");

        _context.Entities.Add(new Entity
        {
            UeiSam = "UEI000000001",
            LegalBusinessName = "Acme Corporation",
            RegistrationStatus = "A"
        });
        _context.SaveChanges();

        var result = await _service.GetDetailAsync("CONTRACT-001");

        result.Should().NotBeNull();
        result!.VendorProfile.Should().NotBeNull();
        result.VendorProfile!.LegalBusinessName.Should().Be("Acme Corporation");
        result.VendorProfile.UeiSam.Should().Be("UEI000000001");
    }

    // -----------------------------------------------------------------------
    // GetBurnRateAsync Tests
    //
    // Note: GetBurnRateAsync uses raw SQL (DATE_FORMAT, GROUP BY) which is not
    // supported by the InMemory provider. The method finds the USASpending award
    // by Piid, then runs a raw SQL query. We can test the "not found" case.
    // -----------------------------------------------------------------------

    [Fact]
    public async Task GetBurnRateAsync_NonexistentContract_ReturnsNull()
    {
        var result = await _service.GetBurnRateAsync("NONEXISTENT");

        result.Should().BeNull();
    }
}
