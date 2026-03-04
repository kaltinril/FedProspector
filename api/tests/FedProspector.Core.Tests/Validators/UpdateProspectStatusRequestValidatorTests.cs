using FluentAssertions;
using FluentValidation.TestHelper;
using FedProspector.Core.DTOs.Prospects;
using FedProspector.Core.Validators;

namespace FedProspector.Core.Tests.Validators;

public class UpdateProspectStatusRequestValidatorTests
{
    private readonly UpdateProspectStatusRequestValidator _validator = new();

    [Theory]
    [InlineData("NEW")]
    [InlineData("REVIEWING")]
    [InlineData("PURSUING")]
    [InlineData("BID_SUBMITTED")]
    [InlineData("WON")]
    [InlineData("LOST")]
    [InlineData("DECLINED")]
    [InlineData("NO_BID")]
    public void Validate_ValidStatus_ShouldPass(string status)
    {
        var request = new UpdateProspectStatusRequest { NewStatus = status };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveAnyValidationErrors();
    }

    [Theory]
    [InlineData("")]
    [InlineData(null)]
    public void Validate_EmptyNewStatus_ShouldFail(string? status)
    {
        var request = new UpdateProspectStatusRequest { NewStatus = status! };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.NewStatus);
    }

    [Theory]
    [InlineData("ACTIVE")]
    [InlineData("INVALID")]
    [InlineData("PENDING")]
    public void Validate_InvalidStatus_ShouldFail(string status)
    {
        var request = new UpdateProspectStatusRequest { NewStatus = status };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.NewStatus);
    }
}
