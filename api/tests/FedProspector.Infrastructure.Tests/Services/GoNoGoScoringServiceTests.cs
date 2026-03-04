using FedProspector.Core.Models;
using FedProspector.Infrastructure.Data;
using FedProspector.Infrastructure.Services;
using FluentAssertions;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging.Abstractions;

namespace FedProspector.Infrastructure.Tests.Services;

public class GoNoGoScoringServiceTests : IDisposable
{
    private readonly FedProspectorDbContext _context;
    private readonly GoNoGoScoringService _service;

    public GoNoGoScoringServiceTests()
    {
        var options = new DbContextOptionsBuilder<FedProspectorDbContext>()
            .UseInMemoryDatabase(databaseName: Guid.NewGuid().ToString())
            .Options;

        _context = new FedProspectorDbContext(options);
        _service = new GoNoGoScoringService(_context, NullLogger<GoNoGoScoringService>.Instance);
    }

    public void Dispose()
    {
        _context.Dispose();
    }

    private void SeedProspectWithOpportunity(
        int prospectId = 1,
        string noticeId = "NOTICE-001",
        string? setAsideCode = null,
        string? naicsCode = null,
        DateTime? responseDeadline = null,
        decimal? awardAmount = null,
        decimal? estimatedValue = null)
    {
        _context.Prospects.Add(new Prospect
        {
            ProspectId = prospectId,
            OrganizationId = 1,
            NoticeId = noticeId,
            Status = "NEW",
            EstimatedValue = estimatedValue
        });

        _context.Opportunities.Add(new Opportunity
        {
            NoticeId = noticeId,
            SetAsideCode = setAsideCode,
            NaicsCode = naicsCode,
            ResponseDeadline = responseDeadline,
            AwardAmount = awardAmount
        });

        _context.SaveChanges();
    }

    // --- Set-aside scoring ---

    [Fact]
    public async Task CalculateScoreAsync_WosbSetAside_ReturnsSetAsideScore10()
    {
        SeedProspectWithOpportunity(setAsideCode: "WOSB");

        var result = await _service.CalculateScoreAsync(1);

        result.Breakdown.SetAside.Score.Should().Be(10);
        result.Breakdown.SetAside.Detail.Should().Contain("WOSB");
    }

    [Fact]
    public async Task CalculateScoreAsync_EdwosbSetAside_ReturnsSetAsideScore10()
    {
        SeedProspectWithOpportunity(setAsideCode: "EDWOSB");

        var result = await _service.CalculateScoreAsync(1);

        result.Breakdown.SetAside.Score.Should().Be(10);
    }

    [Fact]
    public async Task CalculateScoreAsync_8aSetAside_ReturnsSetAsideScore8()
    {
        SeedProspectWithOpportunity(setAsideCode: "8A");

        var result = await _service.CalculateScoreAsync(1);

        result.Breakdown.SetAside.Score.Should().Be(8);
        result.Breakdown.SetAside.Detail.Should().Contain("8A");
    }

    [Fact]
    public async Task CalculateScoreAsync_8anSetAside_ReturnsSetAsideScore8()
    {
        SeedProspectWithOpportunity(setAsideCode: "8AN");

        var result = await _service.CalculateScoreAsync(1);

        result.Breakdown.SetAside.Score.Should().Be(8);
    }

    [Fact]
    public async Task CalculateScoreAsync_NoSetAside_ReturnsSetAsideScore0()
    {
        SeedProspectWithOpportunity(setAsideCode: null);

        var result = await _service.CalculateScoreAsync(1);

        result.Breakdown.SetAside.Score.Should().Be(0);
    }

    // --- Time remaining scoring ---

    [Fact]
    public async Task CalculateScoreAsync_DeadlineOver30Days_ReturnsTimeScore10()
    {
        SeedProspectWithOpportunity(responseDeadline: DateTime.UtcNow.AddDays(45));

        var result = await _service.CalculateScoreAsync(1);

        result.Breakdown.TimeRemaining.Score.Should().Be(10);
    }

    [Fact]
    public async Task CalculateScoreAsync_DeadlineWithin30Days_ReturnsTimeScore7()
    {
        SeedProspectWithOpportunity(responseDeadline: DateTime.UtcNow.AddDays(20));

        var result = await _service.CalculateScoreAsync(1);

        result.Breakdown.TimeRemaining.Score.Should().Be(7);
    }

    [Fact]
    public async Task CalculateScoreAsync_DeadlineWithin14Days_ReturnsTimeScore4()
    {
        SeedProspectWithOpportunity(responseDeadline: DateTime.UtcNow.AddDays(10));

        var result = await _service.CalculateScoreAsync(1);

        result.Breakdown.TimeRemaining.Score.Should().Be(4);
    }

    [Fact]
    public async Task CalculateScoreAsync_DeadlineWithin7Days_ReturnsTimeScore1()
    {
        SeedProspectWithOpportunity(responseDeadline: DateTime.UtcNow.AddDays(3));

        var result = await _service.CalculateScoreAsync(1);

        result.Breakdown.TimeRemaining.Score.Should().Be(1);
    }

    [Fact]
    public async Task CalculateScoreAsync_DeadlinePassed_ReturnsTimeScore0()
    {
        SeedProspectWithOpportunity(responseDeadline: DateTime.UtcNow.AddDays(-5));

        var result = await _service.CalculateScoreAsync(1);

        result.Breakdown.TimeRemaining.Score.Should().Be(0);
    }

    [Fact]
    public async Task CalculateScoreAsync_NoDeadline_ReturnsTimeScore5()
    {
        SeedProspectWithOpportunity(responseDeadline: null);

        var result = await _service.CalculateScoreAsync(1);

        result.Breakdown.TimeRemaining.Score.Should().Be(5);
        result.Breakdown.TimeRemaining.Detail.Should().Contain("No deadline");
    }

    // --- Award value scoring ---

    [Fact]
    public async Task CalculateScoreAsync_AwardValueOver1M_ReturnsValueScore10()
    {
        SeedProspectWithOpportunity(awardAmount: 2_000_000m);

        var result = await _service.CalculateScoreAsync(1);

        result.Breakdown.AwardValue.Score.Should().Be(10);
    }

    [Fact]
    public async Task CalculateScoreAsync_AwardValue500K_ReturnsValueScore8()
    {
        SeedProspectWithOpportunity(awardAmount: 750_000m);

        var result = await _service.CalculateScoreAsync(1);

        result.Breakdown.AwardValue.Score.Should().Be(8);
    }

    [Fact]
    public async Task CalculateScoreAsync_AwardValue100K_ReturnsValueScore6()
    {
        SeedProspectWithOpportunity(awardAmount: 250_000m);

        var result = await _service.CalculateScoreAsync(1);

        result.Breakdown.AwardValue.Score.Should().Be(6);
    }

    [Fact]
    public async Task CalculateScoreAsync_AwardValue50K_ReturnsValueScore4()
    {
        SeedProspectWithOpportunity(awardAmount: 75_000m);

        var result = await _service.CalculateScoreAsync(1);

        result.Breakdown.AwardValue.Score.Should().Be(4);
    }

    [Fact]
    public async Task CalculateScoreAsync_AwardValueBelow50K_ReturnsValueScore2()
    {
        SeedProspectWithOpportunity(awardAmount: 10_000m);

        var result = await _service.CalculateScoreAsync(1);

        result.Breakdown.AwardValue.Score.Should().Be(2);
    }

    [Fact]
    public async Task CalculateScoreAsync_NoAwardValueUsesEstimatedValue()
    {
        SeedProspectWithOpportunity(awardAmount: null, estimatedValue: 1_500_000m);

        var result = await _service.CalculateScoreAsync(1);

        result.Breakdown.AwardValue.Score.Should().Be(10);
    }

    [Fact]
    public async Task CalculateScoreAsync_NoValueAtAll_ReturnsValueScore3()
    {
        SeedProspectWithOpportunity(awardAmount: null, estimatedValue: null);

        var result = await _service.CalculateScoreAsync(1);

        result.Breakdown.AwardValue.Score.Should().Be(3);
        result.Breakdown.AwardValue.Detail.Should().Contain("Unknown value");
    }

    // --- Missing prospect ---

    [Fact]
    public async Task CalculateScoreAsync_ProspectNotFound_ThrowsKeyNotFoundException()
    {
        // No data seeded

        var act = () => _service.CalculateScoreAsync(999);

        await act.Should().ThrowAsync<KeyNotFoundException>()
            .WithMessage("*999*");
    }

    // --- Total score structure ---

    [Fact]
    public async Task CalculateScoreAsync_ReturnsCorrectTotalAndPercentage()
    {
        SeedProspectWithOpportunity(
            setAsideCode: "WOSB",          // 10 pts
            responseDeadline: DateTime.UtcNow.AddDays(45), // 10 pts
            awardAmount: 2_000_000m         // 10 pts
            // NAICS match = 0 pts (no entity data)
        );

        var result = await _service.CalculateScoreAsync(1);

        result.ProspectId.Should().Be(1);
        result.TotalScore.Should().Be(30);
        result.MaxScore.Should().Be(40);
        result.Percentage.Should().Be(75.0m);
    }

    [Fact]
    public async Task CalculateScoreAsync_UpdatesProspectGoNoGoScore()
    {
        SeedProspectWithOpportunity(setAsideCode: "WOSB", awardAmount: 1_000_000m);

        await _service.CalculateScoreAsync(1);

        var prospect = await _context.Prospects.FindAsync(1);
        prospect!.GoNoGoScore.Should().NotBeNull();
    }

    // --- NAICS match scoring ---

    [Fact]
    public async Task CalculateScoreAsync_NaicsMatchWithWosbEntity_ReturnsNaicsScore10()
    {
        SeedProspectWithOpportunity(naicsCode: "541512");

        _context.EntityNaicsCodes.Add(new EntityNaics
        {
            UeiSam = "UEI000000001",
            NaicsCode = "541512"
        });
        _context.EntityBusinessTypes.Add(new EntityBusinessType
        {
            UeiSam = "UEI000000001",
            BusinessTypeCode = "2X"
        });
        _context.SaveChanges();

        var result = await _service.CalculateScoreAsync(1);

        result.Breakdown.NaicsMatch.Score.Should().Be(10);
        result.Breakdown.NaicsMatch.Detail.Should().Contain("MATCH");
    }

    [Fact]
    public async Task CalculateScoreAsync_NaicsNoMatch_ReturnsNaicsScore0()
    {
        SeedProspectWithOpportunity(naicsCode: "541512");

        // Entity with different NAICS
        _context.EntityNaicsCodes.Add(new EntityNaics
        {
            UeiSam = "UEI000000001",
            NaicsCode = "999999"
        });
        _context.EntityBusinessTypes.Add(new EntityBusinessType
        {
            UeiSam = "UEI000000001",
            BusinessTypeCode = "2X"
        });
        _context.SaveChanges();

        var result = await _service.CalculateScoreAsync(1);

        result.Breakdown.NaicsMatch.Score.Should().Be(0);
        result.Breakdown.NaicsMatch.Detail.Should().Contain("no match");
    }
}
