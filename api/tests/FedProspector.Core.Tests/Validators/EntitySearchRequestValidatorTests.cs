using FluentAssertions;
using FluentValidation.TestHelper;
using FedProspector.Core.DTOs.Entities;
using FedProspector.Core.Validators;

namespace FedProspector.Core.Tests.Validators;

public class EntitySearchRequestValidatorTests
{
    private readonly EntitySearchRequestValidator _validator = new();

    [Fact]
    public void Validate_DefaultRequest_ShouldPass()
    {
        var request = new EntitySearchRequest();
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveAnyValidationErrors();
    }

    [Fact]
    public void Validate_ValidUei_ShouldPass()
    {
        var request = new EntitySearchRequest { Uei = "ABCDEF123456" };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveValidationErrorFor(x => x.Uei);
    }

    [Fact]
    public void Validate_UeiWrongLength_ShouldFail()
    {
        var request = new EntitySearchRequest { Uei = "ABC" };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Uei);
    }

    [Fact]
    public void Validate_RegistrationStatusExactlyOneChar_ShouldPass()
    {
        var request = new EntitySearchRequest { RegistrationStatus = "A" };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveValidationErrorFor(x => x.RegistrationStatus);
    }

    [Fact]
    public void Validate_RegistrationStatusTooLong_ShouldFail()
    {
        var request = new EntitySearchRequest { RegistrationStatus = "AB" };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.RegistrationStatus);
    }

    [Theory]
    [InlineData("54")]
    [InlineData("541")]
    [InlineData("5415")]
    [InlineData("54151")]
    [InlineData("541511")]
    public void Validate_NaicsValidLengths_ShouldPass(string naics)
    {
        var request = new EntitySearchRequest { Naics = naics };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveValidationErrorFor(x => x.Naics);
    }

    [Fact]
    public void Validate_NaicsTooShort_ShouldFail()
    {
        var request = new EntitySearchRequest { Naics = "5" };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Naics);
    }

    [Fact]
    public void Validate_NaicsTooLong_ShouldFail()
    {
        var request = new EntitySearchRequest { Naics = "5415111" };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Naics);
    }

    [Fact]
    public void Validate_AllNullOptionalFields_ShouldPass()
    {
        var request = new EntitySearchRequest
        {
            Uei = null,
            Naics = null,
            RegistrationStatus = null
        };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveAnyValidationErrors();
    }
}
