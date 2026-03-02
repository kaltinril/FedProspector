using FluentAssertions;
using FluentValidation.TestHelper;
using FedProspector.Core.DTOs.Opportunities;
using FedProspector.Core.Validators;

namespace FedProspector.Core.Tests.Validators;

public class TargetOpportunitySearchRequestValidatorTests
{
    private readonly TargetOpportunitySearchRequestValidator _validator = new();

    [Fact]
    public void Validate_DefaultRequest_ShouldPass()
    {
        var request = new TargetOpportunitySearchRequest();
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveAnyValidationErrors();
    }

    [Fact]
    public void Validate_ValidMinAndMaxValue_ShouldPass()
    {
        var request = new TargetOpportunitySearchRequest { MinValue = 100, MaxValue = 500 };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveAnyValidationErrors();
    }

    [Fact]
    public void Validate_MinValueNegative_ShouldFail()
    {
        var request = new TargetOpportunitySearchRequest { MinValue = -1 };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.MinValue);
    }

    [Fact]
    public void Validate_MaxValueLessThanMinValue_ShouldFail()
    {
        var request = new TargetOpportunitySearchRequest { MinValue = 500, MaxValue = 100 };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.MaxValue);
    }

    [Fact]
    public void Validate_MaxValueEqualToMinValue_ShouldPass()
    {
        var request = new TargetOpportunitySearchRequest { MinValue = 100, MaxValue = 100 };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveAnyValidationErrors();
    }

    [Fact]
    public void Validate_MaxValueWithoutMinValue_ShouldPass()
    {
        var request = new TargetOpportunitySearchRequest { MaxValue = 500 };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveAnyValidationErrors();
    }

    [Fact]
    public void Validate_MinValueZero_ShouldPass()
    {
        var request = new TargetOpportunitySearchRequest { MinValue = 0 };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveAnyValidationErrors();
    }
}
