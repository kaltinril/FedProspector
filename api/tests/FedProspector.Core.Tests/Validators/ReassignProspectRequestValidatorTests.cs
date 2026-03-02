using FluentAssertions;
using FluentValidation.TestHelper;
using FedProspector.Core.DTOs.Prospects;
using FedProspector.Core.Validators;

namespace FedProspector.Core.Tests.Validators;

public class ReassignProspectRequestValidatorTests
{
    private readonly ReassignProspectRequestValidator _validator = new();

    [Fact]
    public void Validate_ValidRequest_ShouldPass()
    {
        var request = new ReassignProspectRequest { NewAssignedTo = 1 };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveAnyValidationErrors();
    }

    [Fact]
    public void Validate_NewAssignedToZero_ShouldFail()
    {
        var request = new ReassignProspectRequest { NewAssignedTo = 0 };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.NewAssignedTo);
    }

    [Fact]
    public void Validate_NewAssignedToNegative_ShouldFail()
    {
        var request = new ReassignProspectRequest { NewAssignedTo = -1 };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.NewAssignedTo);
    }
}
