using FluentAssertions;
using FluentValidation.TestHelper;
using FedProspector.Core.DTOs;
using FedProspector.Core.Validators;

namespace FedProspector.Core.Tests.Validators;

public class UpdateProfileRequestValidatorTests
{
    private readonly UpdateProfileRequestValidator _validator = new();

    [Fact]
    public void Validate_AllNullFields_ShouldPass()
    {
        var request = new UpdateProfileRequest { DisplayName = null, Email = null };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveAnyValidationErrors();
    }

    [Fact]
    public void Validate_ValidDisplayName_ShouldPass()
    {
        var request = new UpdateProfileRequest { DisplayName = "New Name" };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveValidationErrorFor(x => x.DisplayName);
    }

    [Fact]
    public void Validate_DisplayNameTooLong_ShouldFail()
    {
        var request = new UpdateProfileRequest { DisplayName = new string('x', 101) };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.DisplayName);
    }

    [Fact]
    public void Validate_ValidEmail_ShouldPass()
    {
        var request = new UpdateProfileRequest { Email = "user@example.com", CurrentPassword = "pass" };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveValidationErrorFor(x => x.Email);
    }

    [Fact]
    public void Validate_InvalidEmailFormat_ShouldFail()
    {
        var request = new UpdateProfileRequest { Email = "not-an-email", CurrentPassword = "pass" };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Email);
    }

    [Fact]
    public void Validate_EmailTooLong_ShouldFail()
    {
        var request = new UpdateProfileRequest { Email = new string('a', 192) + "@test.com", CurrentPassword = "pass" };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Email);
    }

    [Fact]
    public void Validate_EmailWithoutCurrentPassword_ShouldFail()
    {
        var request = new UpdateProfileRequest { Email = "new@example.com" };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.CurrentPassword);
    }

    [Fact]
    public void Validate_EmailWithCurrentPassword_ShouldPass()
    {
        var request = new UpdateProfileRequest { Email = "new@example.com", CurrentPassword = "mypassword" };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveValidationErrorFor(x => x.CurrentPassword);
    }

    [Fact]
    public void Validate_NoEmailChange_CurrentPasswordNotRequired()
    {
        var request = new UpdateProfileRequest { DisplayName = "New Name" };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveValidationErrorFor(x => x.CurrentPassword);
    }
}
