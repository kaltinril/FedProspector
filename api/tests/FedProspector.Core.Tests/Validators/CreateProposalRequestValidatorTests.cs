using FluentAssertions;
using FluentValidation.TestHelper;
using FedProspector.Core.DTOs.Proposals;
using FedProspector.Core.Validators;

namespace FedProspector.Core.Tests.Validators;

public class CreateProposalRequestValidatorTests
{
    private readonly CreateProposalRequestValidator _validator = new();

    [Fact]
    public void Validate_ValidRequest_ShouldPass()
    {
        var request = new CreateProposalRequest { ProspectId = 1 };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveAnyValidationErrors();
    }

    [Fact]
    public void Validate_ProspectIdZero_ShouldFail()
    {
        var request = new CreateProposalRequest { ProspectId = 0 };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.ProspectId);
    }

    [Fact]
    public void Validate_ProspectIdNegative_ShouldFail()
    {
        var request = new CreateProposalRequest { ProspectId = -1 };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.ProspectId);
    }
}
