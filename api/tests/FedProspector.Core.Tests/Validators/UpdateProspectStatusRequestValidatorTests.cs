using FluentAssertions;
using FluentValidation.TestHelper;
using FedProspector.Core.DTOs.Prospects;
using FedProspector.Core.Validators;

namespace FedProspector.Core.Tests.Validators;

public class UpdateProspectStatusRequestValidatorTests
{
    private readonly UpdateProspectStatusRequestValidator _validator = new();

    [Fact]
    public void Validate_ValidRequest_ShouldPass()
    {
        var request = new UpdateProspectStatusRequest { NewStatus = "ACTIVE" };
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
}
