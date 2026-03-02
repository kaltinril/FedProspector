using FluentAssertions;
using FluentValidation.TestHelper;
using FedProspector.Core.DTOs;
using FedProspector.Core.Validators;

namespace FedProspector.Core.Tests.Validators;

public class RegisterRequestValidatorTests
{
    private readonly RegisterRequestValidator _validator = new();

    [Fact]
    public void Validate_ValidRequest_ShouldPass()
    {
        var request = new RegisterRequest
        {
            Username = "testuser",
            Email = "test@example.com",
            Password = "Password1",
            DisplayName = "Test User"
        };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveAnyValidationErrors();
    }

    // --- Username rules ---

    [Theory]
    [InlineData("")]
    [InlineData(null)]
    public void Validate_EmptyUsername_ShouldFail(string? username)
    {
        var request = ValidRequest();
        request.Username = username!;
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Username);
    }

    [Fact]
    public void Validate_UsernameTooShort_ShouldFail()
    {
        var request = ValidRequest();
        request.Username = "ab";
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Username);
    }

    [Fact]
    public void Validate_UsernameTooLong_ShouldFail()
    {
        var request = ValidRequest();
        request.Username = new string('a', 51);
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Username);
    }

    [Fact]
    public void Validate_UsernameWithSpecialChars_ShouldFail()
    {
        var request = ValidRequest();
        request.Username = "user@name";
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Username);
    }

    [Fact]
    public void Validate_UsernameWithUnderscores_ShouldPass()
    {
        var request = ValidRequest();
        request.Username = "user_name_123";
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveValidationErrorFor(x => x.Username);
    }

    // --- Email rules ---

    [Theory]
    [InlineData("")]
    [InlineData(null)]
    public void Validate_EmptyEmail_ShouldFail(string? email)
    {
        var request = ValidRequest();
        request.Email = email!;
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Email);
    }

    [Fact]
    public void Validate_InvalidEmailFormat_ShouldFail()
    {
        var request = ValidRequest();
        request.Email = "not-an-email";
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Email);
    }

    [Fact]
    public void Validate_EmailTooLong_ShouldFail()
    {
        var request = ValidRequest();
        request.Email = new string('a', 192) + "@test.com";
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Email);
    }

    // --- Password rules ---

    [Theory]
    [InlineData("")]
    [InlineData(null)]
    public void Validate_EmptyPassword_ShouldFail(string? password)
    {
        var request = ValidRequest();
        request.Password = password!;
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Password);
    }

    [Fact]
    public void Validate_PasswordTooShort_ShouldFail()
    {
        var request = ValidRequest();
        request.Password = "Pass1";
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Password);
    }

    [Fact]
    public void Validate_PasswordTooLong_ShouldFail()
    {
        var request = ValidRequest();
        request.Password = "P1" + new string('a', 127);
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Password);
    }

    [Fact]
    public void Validate_PasswordNoUppercase_ShouldFail()
    {
        var request = ValidRequest();
        request.Password = "password1";
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Password);
    }

    [Fact]
    public void Validate_PasswordNoLowercase_ShouldFail()
    {
        var request = ValidRequest();
        request.Password = "PASSWORD1";
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Password);
    }

    [Fact]
    public void Validate_PasswordNoDigit_ShouldFail()
    {
        var request = ValidRequest();
        request.Password = "Passwordx";
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Password);
    }

    // --- DisplayName rules ---

    [Theory]
    [InlineData("")]
    [InlineData(null)]
    public void Validate_EmptyDisplayName_ShouldFail(string? name)
    {
        var request = ValidRequest();
        request.DisplayName = name!;
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.DisplayName);
    }

    [Fact]
    public void Validate_DisplayNameTooLong_ShouldFail()
    {
        var request = ValidRequest();
        request.DisplayName = new string('x', 101);
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.DisplayName);
    }

    private static RegisterRequest ValidRequest() => new()
    {
        Username = "testuser",
        Email = "test@example.com",
        Password = "Password1",
        DisplayName = "Test User"
    };
}
