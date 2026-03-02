using FluentAssertions;
using FluentValidation.TestHelper;
using FedProspector.Core.DTOs.Opportunities;
using FedProspector.Core.Validators;

namespace FedProspector.Core.Tests.Validators;

public class OpportunitySearchRequestValidatorTests
{
    private readonly OpportunitySearchRequestValidator _validator = new();

    [Fact]
    public void Validate_DefaultRequest_ShouldPass()
    {
        var request = new OpportunitySearchRequest();
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveAnyValidationErrors();
    }

    [Fact]
    public void Validate_ValidOptionalFields_ShouldPass()
    {
        var request = new OpportunitySearchRequest
        {
            DaysOut = 30,
            Naics = "541511",
            State = "VA"
        };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveAnyValidationErrors();
    }

    [Fact]
    public void Validate_DaysOutZero_ShouldFail()
    {
        var request = new OpportunitySearchRequest { DaysOut = 0 };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.DaysOut);
    }

    [Fact]
    public void Validate_DaysOutNegative_ShouldFail()
    {
        var request = new OpportunitySearchRequest { DaysOut = -1 };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.DaysOut);
    }

    [Fact]
    public void Validate_NaicsTooShort_ShouldFail()
    {
        var request = new OpportunitySearchRequest { Naics = "5" };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Naics);
    }

    [Fact]
    public void Validate_NaicsTooLong_ShouldFail()
    {
        var request = new OpportunitySearchRequest { Naics = "5415111" };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Naics);
    }

    [Theory]
    [InlineData("54")]
    [InlineData("541")]
    [InlineData("5415")]
    [InlineData("54151")]
    [InlineData("541511")]
    public void Validate_NaicsValidLengths_ShouldPass(string naics)
    {
        var request = new OpportunitySearchRequest { Naics = naics };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveValidationErrorFor(x => x.Naics);
    }

    [Fact]
    public void Validate_StateTooShort_ShouldFail()
    {
        var request = new OpportunitySearchRequest { State = "V" };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.State);
    }

    [Fact]
    public void Validate_StateTooLong_ShouldFail()
    {
        var request = new OpportunitySearchRequest { State = "VAA" };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.State);
    }

    [Fact]
    public void Validate_StateExactlyTwoChars_ShouldPass()
    {
        var request = new OpportunitySearchRequest { State = "VA" };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveValidationErrorFor(x => x.State);
    }

    [Fact]
    public void Validate_NullOptionalFields_ShouldPass()
    {
        var request = new OpportunitySearchRequest
        {
            DaysOut = null,
            Naics = null,
            State = null
        };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveAnyValidationErrors();
    }
}
