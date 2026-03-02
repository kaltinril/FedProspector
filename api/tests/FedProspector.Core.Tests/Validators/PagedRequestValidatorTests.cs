using FluentAssertions;
using FluentValidation.TestHelper;
using FedProspector.Core.DTOs;
using FedProspector.Core.Validators;

namespace FedProspector.Core.Tests.Validators;

public class PagedRequestValidatorTests
{
    private readonly PagedRequestValidator _validator = new();

    [Fact]
    public void Validate_DefaultValues_ShouldPass()
    {
        var request = new PagedRequest();
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveAnyValidationErrors();
    }

    [Theory]
    [InlineData(1, 1)]
    [InlineData(1, 50)]
    [InlineData(1, 100)]
    [InlineData(999, 25)]
    public void Validate_ValidPageAndPageSize_ShouldPass(int page, int pageSize)
    {
        var request = new PagedRequest { Page = page, PageSize = pageSize };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveAnyValidationErrors();
    }

    [Fact]
    public void PagedRequest_PageBelowOne_ClampedToOne()
    {
        // PagedRequest clamps Page to 1 in its setter, so validator always sees >= 1
        var request = new PagedRequest { Page = -5 };
        request.Page.Should().Be(1);
    }

    [Fact]
    public void PagedRequest_PageSizeAbove100_ClampedTo100()
    {
        var request = new PagedRequest { PageSize = 200 };
        request.PageSize.Should().Be(100);
    }

    [Fact]
    public void PagedRequest_PageSizeBelowOne_ClampedToOne()
    {
        var request = new PagedRequest { PageSize = 0 };
        request.PageSize.Should().Be(1);
    }
}
