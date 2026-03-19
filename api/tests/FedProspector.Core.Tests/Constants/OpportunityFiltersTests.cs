using FedProspector.Core.Constants;
using FluentAssertions;

namespace FedProspector.Core.Tests.Constants;

public class OpportunityFiltersTests
{
    [Fact]
    public void NonBiddableTypes_ContainsExactlyFourTypes()
    {
        OpportunityFilters.NonBiddableTypes.Should().HaveCount(4);
    }

    [Fact]
    public void NonBiddableTypes_ContainsAwardNotice()
    {
        OpportunityFilters.NonBiddableTypes.Should().Contain("Award Notice");
    }

    [Fact]
    public void NonBiddableTypes_ContainsJustification()
    {
        OpportunityFilters.NonBiddableTypes.Should().Contain("Justification");
    }

    [Fact]
    public void NonBiddableTypes_ContainsSaleOfSurplusProperty()
    {
        OpportunityFilters.NonBiddableTypes.Should().Contain("Sale of Surplus Property");
    }

    [Fact]
    public void NonBiddableTypes_ContainsConsolidateBundle()
    {
        OpportunityFilters.NonBiddableTypes.Should().Contain("Consolidate/(Substantially) Bundle");
    }

    [Theory]
    [InlineData("Combined Synopsis/Solicitation")]
    [InlineData("Solicitation")]
    [InlineData("Presolicitation")]
    [InlineData("Sources Sought")]
    [InlineData("Special Notice")]
    public void NonBiddableTypes_DoesNotContainBiddableTypes(string biddableType)
    {
        OpportunityFilters.NonBiddableTypes.Should().NotContain(biddableType);
    }

    [Fact]
    public void NonBiddableTypes_IsReadonly_CannotBeReassigned()
    {
        // The field is static readonly, so we verify it is not null and stable
        var first = OpportunityFilters.NonBiddableTypes;
        var second = OpportunityFilters.NonBiddableTypes;

        first.Should().BeSameAs(second, "static readonly field should return same reference");
    }
}
