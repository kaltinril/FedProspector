using FluentAssertions;
using FluentValidation.TestHelper;
using FedProspector.Core.DTOs.Proposals;
using FedProspector.Core.Validators;

namespace FedProspector.Core.Tests.Validators;

public class UpdateMilestoneRequestValidatorTests
{
    private readonly UpdateMilestoneRequestValidator _validator = new();

    [Fact]
    public void Validate_NullStatus_ShouldPass()
    {
        var request = new UpdateMilestoneRequest { Status = null };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveValidationErrorFor(x => x.Status);
    }

    [Theory]
    [InlineData("PENDING")]
    [InlineData("IN_PROGRESS")]
    [InlineData("COMPLETED")]
    [InlineData("SKIPPED")]
    public void Validate_ValidStatus_ShouldPass(string status)
    {
        var request = new UpdateMilestoneRequest { Status = status };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveValidationErrorFor(x => x.Status);
    }

    [Fact]
    public void Validate_InvalidStatus_ShouldFail()
    {
        var request = new UpdateMilestoneRequest { Status = "DONE" };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Status);
    }

    [Fact]
    public void Validate_LowercaseStatus_ShouldFail()
    {
        var request = new UpdateMilestoneRequest { Status = "pending" };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Status);
    }
}
