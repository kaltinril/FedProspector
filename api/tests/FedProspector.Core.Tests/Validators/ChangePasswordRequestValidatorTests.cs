using FluentAssertions;
using FluentValidation.TestHelper;
using FedProspector.Core.DTOs;
using FedProspector.Core.Validators;

namespace FedProspector.Core.Tests.Validators;

public class ChangePasswordRequestValidatorTests
{
    private readonly ChangePasswordRequestValidator _validator = new();

    [Fact]
    public void Validate_ValidRequest_ShouldPass()
    {
        var request = new ChangePasswordRequest
        {
            CurrentPassword = "oldpass1",
            NewPassword = "NewPass1x"
        };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveAnyValidationErrors();
    }

    [Theory]
    [InlineData("")]
    [InlineData(null)]
    public void Validate_EmptyCurrentPassword_ShouldFail(string? current)
    {
        var request = new ChangePasswordRequest { CurrentPassword = current!, NewPassword = "NewPass1x" };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.CurrentPassword);
    }

    [Theory]
    [InlineData("")]
    [InlineData(null)]
    public void Validate_EmptyNewPassword_ShouldFail(string? newPw)
    {
        var request = new ChangePasswordRequest { CurrentPassword = "oldpass", NewPassword = newPw! };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.NewPassword);
    }

    [Fact]
    public void Validate_NewPasswordTooShort_ShouldFail()
    {
        var request = new ChangePasswordRequest { CurrentPassword = "old", NewPassword = "Pass1" };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.NewPassword);
    }

    [Fact]
    public void Validate_NewPasswordTooLong_ShouldFail()
    {
        var request = new ChangePasswordRequest
        {
            CurrentPassword = "old",
            NewPassword = "P1" + new string('a', 127)
        };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.NewPassword);
    }

    [Fact]
    public void Validate_NewPasswordNoUppercase_ShouldFail()
    {
        var request = new ChangePasswordRequest { CurrentPassword = "old", NewPassword = "password1" };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.NewPassword);
    }

    [Fact]
    public void Validate_NewPasswordNoLowercase_ShouldFail()
    {
        var request = new ChangePasswordRequest { CurrentPassword = "old", NewPassword = "PASSWORD1" };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.NewPassword);
    }

    [Fact]
    public void Validate_NewPasswordNoDigit_ShouldFail()
    {
        var request = new ChangePasswordRequest { CurrentPassword = "old", NewPassword = "Passwordx" };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.NewPassword);
    }
}
