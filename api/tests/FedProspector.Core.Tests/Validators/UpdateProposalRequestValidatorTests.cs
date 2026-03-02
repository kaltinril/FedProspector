using FluentAssertions;
using FluentValidation.TestHelper;
using FedProspector.Core.DTOs.Proposals;
using FedProspector.Core.Validators;

namespace FedProspector.Core.Tests.Validators;

public class UpdateProposalRequestValidatorTests
{
    private readonly UpdateProposalRequestValidator _validator = new();

    [Fact]
    public void Validate_NullStatus_ShouldPass()
    {
        var request = new UpdateProposalRequest { Status = null };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveValidationErrorFor(x => x.Status);
    }

    [Theory]
    [InlineData("DRAFT")]
    [InlineData("IN_REVIEW")]
    [InlineData("SUBMITTED")]
    [InlineData("UNDER_EVALUATION")]
    [InlineData("AWARDED")]
    [InlineData("NOT_AWARDED")]
    [InlineData("CANCELLED")]
    public void Validate_ValidStatus_ShouldPass(string status)
    {
        var request = new UpdateProposalRequest { Status = status };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveValidationErrorFor(x => x.Status);
    }

    [Fact]
    public void Validate_InvalidStatus_ShouldFail()
    {
        var request = new UpdateProposalRequest { Status = "INVALID" };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Status);
    }

    [Fact]
    public void Validate_LowercaseStatus_ShouldFail()
    {
        var request = new UpdateProposalRequest { Status = "draft" };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Status);
    }
}
