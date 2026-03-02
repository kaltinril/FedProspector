using FluentAssertions;
using FluentValidation.TestHelper;
using FedProspector.Core.DTOs.Prospects;
using FedProspector.Core.Validators;

namespace FedProspector.Core.Tests.Validators;

public class ProspectSearchRequestValidatorTests
{
    private readonly ProspectSearchRequestValidator _validator = new();

    [Fact]
    public void Validate_DefaultRequest_ShouldPass()
    {
        var request = new ProspectSearchRequest();
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveAnyValidationErrors();
    }

    [Fact]
    public void Validate_StatusTooLong_ShouldFail()
    {
        var request = new ProspectSearchRequest { Status = new string('x', 51) };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Status);
    }

    [Fact]
    public void Validate_StatusExactly50_ShouldPass()
    {
        var request = new ProspectSearchRequest { Status = new string('x', 50) };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveValidationErrorFor(x => x.Status);
    }

    [Fact]
    public void Validate_PriorityTooLong_ShouldFail()
    {
        var request = new ProspectSearchRequest { Priority = new string('x', 21) };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Priority);
    }

    [Fact]
    public void Validate_NaicsTooShort_ShouldFail()
    {
        var request = new ProspectSearchRequest { Naics = "5" };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Naics);
    }

    [Fact]
    public void Validate_NaicsTooLong_ShouldFail()
    {
        var request = new ProspectSearchRequest { Naics = "5415111" };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Naics);
    }

    [Fact]
    public void Validate_SetAsideTooLong_ShouldFail()
    {
        var request = new ProspectSearchRequest { SetAside = new string('x', 51) };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.SetAside);
    }

    [Fact]
    public void Validate_AllNullOptionalFields_ShouldPass()
    {
        var request = new ProspectSearchRequest
        {
            Status = null,
            Priority = null,
            Naics = null,
            SetAside = null
        };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveAnyValidationErrors();
    }
}
