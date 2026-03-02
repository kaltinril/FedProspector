using FluentAssertions;
using FluentValidation.TestHelper;
using FedProspector.Core.DTOs.Prospects;
using FedProspector.Core.Validators;

namespace FedProspector.Core.Tests.Validators;

public class AddTeamMemberRequestValidatorTests
{
    private readonly AddTeamMemberRequestValidator _validator = new();

    [Theory]
    [InlineData("PRIME")]
    [InlineData("SUB")]
    [InlineData("MENTOR")]
    [InlineData("JV_PARTNER")]
    public void Validate_ValidRole_ShouldPass(string role)
    {
        var request = new AddTeamMemberRequest { Role = role };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveAnyValidationErrors();
    }

    [Fact]
    public void Validate_InvalidRole_ShouldFail()
    {
        var request = new AddTeamMemberRequest { Role = "INVALID" };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Role);
    }

    [Theory]
    [InlineData("")]
    [InlineData(null)]
    public void Validate_EmptyRole_ShouldFail(string? role)
    {
        var request = new AddTeamMemberRequest { Role = role! };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Role);
    }

    [Fact]
    public void Validate_LowercaseRole_ShouldFail()
    {
        var request = new AddTeamMemberRequest { Role = "prime" };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Role);
    }
}
