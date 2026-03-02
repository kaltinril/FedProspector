using FluentAssertions;
using FluentValidation.TestHelper;
using FedProspector.Core.DTOs.Awards;
using FedProspector.Core.Validators;

namespace FedProspector.Core.Tests.Validators;

public class AwardSearchRequestValidatorTests
{
    private readonly AwardSearchRequestValidator _validator = new();

    [Fact]
    public void Validate_DefaultRequest_ShouldPass()
    {
        var request = new AwardSearchRequest();
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveAnyValidationErrors();
    }

    [Fact]
    public void Validate_ValidCompleteRequest_ShouldPass()
    {
        var request = new AwardSearchRequest
        {
            MinValue = 100,
            MaxValue = 500,
            DateFrom = new DateOnly(2025, 1, 1),
            DateTo = new DateOnly(2025, 12, 31),
            VendorUei = "ABCDEF123456"
        };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveAnyValidationErrors();
    }

    [Fact]
    public void Validate_MinValueNegative_ShouldFail()
    {
        var request = new AwardSearchRequest { MinValue = -1 };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.MinValue);
    }

    [Fact]
    public void Validate_MaxValueLessThanMinValue_ShouldFail()
    {
        var request = new AwardSearchRequest { MinValue = 500, MaxValue = 100 };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.MaxValue);
    }

    [Fact]
    public void Validate_MaxValueEqualToMinValue_ShouldPass()
    {
        var request = new AwardSearchRequest { MinValue = 100, MaxValue = 100 };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveAnyValidationErrors();
    }

    [Fact]
    public void Validate_DateToBeforeDateFrom_ShouldFail()
    {
        var request = new AwardSearchRequest
        {
            DateFrom = new DateOnly(2025, 12, 31),
            DateTo = new DateOnly(2025, 1, 1)
        };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.DateTo);
    }

    [Fact]
    public void Validate_DateToEqualToDateFrom_ShouldPass()
    {
        var request = new AwardSearchRequest
        {
            DateFrom = new DateOnly(2025, 6, 15),
            DateTo = new DateOnly(2025, 6, 15)
        };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveAnyValidationErrors();
    }

    [Fact]
    public void Validate_DateToWithoutDateFrom_ShouldPass()
    {
        var request = new AwardSearchRequest { DateTo = new DateOnly(2025, 12, 31) };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveAnyValidationErrors();
    }

    [Fact]
    public void Validate_VendorUeiWrongLength_ShouldFail()
    {
        var request = new AwardSearchRequest { VendorUei = "ABC" };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.VendorUei);
    }

    [Fact]
    public void Validate_VendorUeiExactly12_ShouldPass()
    {
        var request = new AwardSearchRequest { VendorUei = "ABCDEF123456" };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveValidationErrorFor(x => x.VendorUei);
    }

    [Fact]
    public void Validate_VendorUeiNull_ShouldPass()
    {
        var request = new AwardSearchRequest { VendorUei = null };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveValidationErrorFor(x => x.VendorUei);
    }
}
