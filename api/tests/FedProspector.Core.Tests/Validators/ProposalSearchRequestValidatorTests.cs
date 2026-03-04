using FluentAssertions;
using FluentValidation.TestHelper;
using FedProspector.Core.DTOs.Proposals;
using FedProspector.Core.Validators;

namespace FedProspector.Core.Tests.Validators;

public class ProposalSearchRequestValidatorTests
{
    private readonly ProposalSearchRequestValidator _validator = new();

    [Fact]
    public void Validate_ValidRequest_ShouldPass()
    {
        var request = new ProposalSearchRequest
        {
            Status = "DRAFT",
            ProspectId = 1
        };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveAnyValidationErrors();
    }

    [Fact]
    public void Validate_NullStatus_ShouldPass()
    {
        var request = new ProposalSearchRequest { Status = null };
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
        var request = new ProposalSearchRequest { Status = status };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveValidationErrorFor(x => x.Status);
    }

    [Fact]
    public void Validate_InvalidStatus_ShouldFail()
    {
        var request = new ProposalSearchRequest { Status = "invalid_value" };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Status);
    }

    [Fact]
    public void Validate_ProspectIdOne_ShouldPass()
    {
        var request = new ProposalSearchRequest { ProspectId = 1 };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveValidationErrorFor(x => x.ProspectId);
    }

    [Fact]
    public void Validate_ProspectIdZero_ShouldFail()
    {
        var request = new ProposalSearchRequest { ProspectId = 0 };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.ProspectId);
    }

    [Fact]
    public void Validate_ProspectIdNegative_ShouldFail()
    {
        var request = new ProposalSearchRequest { ProspectId = -5 };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.ProspectId);
    }

    [Fact]
    public void Validate_ProspectIdNull_ShouldPass()
    {
        var request = new ProposalSearchRequest { ProspectId = null };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveValidationErrorFor(x => x.ProspectId);
    }
}
