using FluentAssertions;
using FluentValidation.TestHelper;
using FedProspector.Core.DTOs.Subawards;
using FedProspector.Core.Validators;

namespace FedProspector.Core.Tests.Validators;

public class TeamingPartnerSearchRequestValidatorTests
{
    private readonly TeamingPartnerSearchRequestValidator _validator = new();

    [Fact]
    public void Validate_DefaultRequest_ShouldPass()
    {
        // Default MinSubawards = 2, which is >= 1
        var request = new TeamingPartnerSearchRequest();
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveAnyValidationErrors();
    }

    [Fact]
    public void Validate_MinSubawardsOne_ShouldPass()
    {
        var request = new TeamingPartnerSearchRequest { MinSubawards = 1 };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveAnyValidationErrors();
    }

    [Fact]
    public void Validate_MinSubawardsZero_ShouldFail()
    {
        var request = new TeamingPartnerSearchRequest { MinSubawards = 0 };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.MinSubawards);
    }

    [Fact]
    public void Validate_MinSubawardsNegative_ShouldFail()
    {
        var request = new TeamingPartnerSearchRequest { MinSubawards = -1 };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.MinSubawards);
    }

    [Fact]
    public void Validate_MinSubawardsLargeValue_ShouldPass()
    {
        var request = new TeamingPartnerSearchRequest { MinSubawards = 1000 };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveAnyValidationErrors();
    }
}
