using FedProspector.Core.Services;
using FluentAssertions;

namespace FedProspector.Core.Tests.Services;

/// <summary>
/// Phase 132: the canonical normalization rule (trim → uppercase → remove dashes)
/// MUST stay identical to the SQL and Python implementations.
/// </summary>
public class IdentifierNormalizerTests
{
    [Theory]
    [InlineData("FA4484-20-S-C002", "FA448420SC002")]   // dashed SAM.gov form
    [InlineData("FA448420SC002", "FA448420SC002")]       // already dashless (FPDS form)
    [InlineData("fa4484-20-s-c002", "FA448420SC002")]    // lowercase normalizes up
    [InlineData("  FA4484-20-S-C002  ", "FA448420SC002")] // surrounding whitespace trimmed
    [InlineData("abc-123", "ABC123")]
    public void Normalize_AppliesTrimUpperDashStrip(string input, string expected)
    {
        IdentifierNormalizer.Normalize(input).Should().Be(expected);
    }

    [Fact]
    public void Normalize_DashedAndDashlessFormsCollapseToSameValue()
    {
        // The whole point of Phase 132: the two government formats of one identifier
        // must produce an identical canonical key.
        var dashed = IdentifierNormalizer.Normalize("FA4484-20-S-C002");
        var dashless = IdentifierNormalizer.Normalize("FA448420SC002");

        dashed.Should().Be(dashless);
    }

    [Fact]
    public void Normalize_Null_ReturnsNull()
    {
        IdentifierNormalizer.Normalize(null).Should().BeNull();
    }

    [Theory]
    [InlineData("")]
    [InlineData("   ")]
    [InlineData("---")]
    public void Normalize_EmptyOrDashOnly_ReturnsEmptyString(string input)
    {
        IdentifierNormalizer.Normalize(input).Should().BeEmpty();
    }
}
