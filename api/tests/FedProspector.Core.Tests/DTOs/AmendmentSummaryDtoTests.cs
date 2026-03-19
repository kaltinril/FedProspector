using FedProspector.Core.DTOs.Opportunities;
using FluentAssertions;

namespace FedProspector.Core.Tests.DTOs;

public class AmendmentSummaryDtoTests
{
    [Fact]
    public void AwardeeName_DefaultsToNull()
    {
        var dto = new AmendmentSummaryDto();

        dto.AwardeeName.Should().BeNull();
    }

    [Fact]
    public void AwardeeName_CanBeSet()
    {
        var dto = new AmendmentSummaryDto { AwardeeName = "Acme Corp" };

        dto.AwardeeName.Should().Be("Acme Corp");
    }

    [Fact]
    public void AwardAmount_DefaultsToNull()
    {
        var dto = new AmendmentSummaryDto();

        dto.AwardAmount.Should().BeNull();
    }

    [Fact]
    public void AwardAmount_CanBeSet()
    {
        var dto = new AmendmentSummaryDto { AwardAmount = 1_500_000.50m };

        dto.AwardAmount.Should().Be(1_500_000.50m);
    }

    [Fact]
    public void AllProperties_CanBePopulated()
    {
        var dto = new AmendmentSummaryDto
        {
            NoticeId = "NOTICE-001",
            Title = "IT Services Amendment",
            Type = "Award Notice",
            PostedDate = new DateOnly(2026, 3, 1),
            ResponseDeadline = new DateTime(2026, 4, 1, 12, 0, 0),
            AwardeeName = "Tech Solutions Inc",
            AwardAmount = 2_500_000m
        };

        dto.NoticeId.Should().Be("NOTICE-001");
        dto.Title.Should().Be("IT Services Amendment");
        dto.Type.Should().Be("Award Notice");
        dto.PostedDate.Should().Be(new DateOnly(2026, 3, 1));
        dto.ResponseDeadline.Should().Be(new DateTime(2026, 4, 1, 12, 0, 0));
        dto.AwardeeName.Should().Be("Tech Solutions Inc");
        dto.AwardAmount.Should().Be(2_500_000m);
    }
}
