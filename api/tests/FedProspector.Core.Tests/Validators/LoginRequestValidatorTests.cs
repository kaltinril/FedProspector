using FluentAssertions;
using FluentValidation.TestHelper;
using FedProspector.Core.DTOs;
using FedProspector.Core.Validators;

namespace FedProspector.Core.Tests.Validators;

public class LoginRequestValidatorTests
{
    private readonly LoginRequestValidator _validator = new();

    [Fact]
    public void Validate_ValidRequest_ShouldPass()
    {
        var request = new LoginRequest { Email = "user@example.com", Password = "password1" };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveAnyValidationErrors();
    }

    [Theory]
    [InlineData("")]
    [InlineData(null)]
    public void Validate_EmptyEmail_ShouldFail(string? email)
    {
        var request = new LoginRequest { Email = email!, Password = "password1" };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Email);
    }

    [Fact]
    public void Validate_InvalidEmailFormat_ShouldFail()
    {
        var request = new LoginRequest { Email = "not-an-email", Password = "password1" };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Email);
    }

    [Fact]
    public void Validate_EmailTooLong_ShouldFail()
    {
        var request = new LoginRequest { Email = new string('a', 192) + "@test.com", Password = "password1" };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Email);
    }

    [Theory]
    [InlineData("")]
    [InlineData(null)]
    public void Validate_EmptyPassword_ShouldFail(string? password)
    {
        var request = new LoginRequest { Email = "user@example.com", Password = password! };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Password);
    }

    [Fact]
    public void Validate_PasswordTooShort_ShouldFail()
    {
        var request = new LoginRequest { Email = "user@example.com", Password = "short" };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Password);
    }

    [Fact]
    public void Validate_PasswordTooLong_ShouldFail()
    {
        var request = new LoginRequest { Email = "user@example.com", Password = new string('a', 129) };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Password);
    }
}
