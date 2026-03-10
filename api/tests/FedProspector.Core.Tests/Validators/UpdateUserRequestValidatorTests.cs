using FluentAssertions;
using FluentValidation.TestHelper;
using FedProspector.Core.DTOs.Admin;
using FedProspector.Core.Validators;

namespace FedProspector.Core.Tests.Validators;

public class UpdateUserRequestValidatorTests
{
    private readonly UpdateUserRequestValidator _validator = new();

    [Fact]
    public void Validate_ValidRoleUser_ShouldPass()
    {
        var request = new UpdateUserRequest { Role = "USER" };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveAnyValidationErrors();
    }

    [Fact]
    public void Validate_ValidRoleAdmin_ShouldPass()
    {
        var request = new UpdateUserRequest { Role = "ADMIN" };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveAnyValidationErrors();
    }

    [Fact]
    public void Validate_InvalidRole_ShouldFail()
    {
        var request = new UpdateUserRequest { Role = "SUPERADMIN" };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Role);
    }

    [Fact]
    public void Validate_IsOrgAdminOnly_ShouldPass()
    {
        var request = new UpdateUserRequest { IsOrgAdmin = true };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveAnyValidationErrors();
    }

    [Fact]
    public void Validate_IsActiveOnly_ShouldPass()
    {
        var request = new UpdateUserRequest { IsActive = false };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveAnyValidationErrors();
    }

    [Fact]
    public void Validate_NoFieldsProvided_ShouldFail()
    {
        var request = new UpdateUserRequest();
        var result = _validator.TestValidate(request);
        result.IsValid.Should().BeFalse();
    }

    [Fact]
    public void Validate_AllFieldsProvided_ShouldPass()
    {
        var request = new UpdateUserRequest { Role = "USER", IsOrgAdmin = false, IsActive = true };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveAnyValidationErrors();
    }
}
