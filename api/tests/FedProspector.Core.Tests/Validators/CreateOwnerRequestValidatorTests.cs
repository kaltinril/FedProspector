using FluentAssertions;
using FluentValidation.TestHelper;
using FedProspector.Core.DTOs.Organizations;
using FedProspector.Core.Validators;

namespace FedProspector.Core.Tests.Validators;

public class CreateOwnerRequestValidatorTests
{
    private readonly CreateOwnerRequestValidator _validator = new();

    [Fact]
    public void Validate_ValidRequest_ShouldPass()
    {
        var request = new CreateOwnerRequest
        {
            Email = "owner@example.com",
            Password = "SecureP1",
            DisplayName = "Jane Owner"
        };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveAnyValidationErrors();
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
        request.Email = new string('a', 247) + "@test.com"; // 256 chars
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Email);
    }

    [Fact]
    public void Validate_EmailExactly255_ShouldPass()
    {
        var request = ValidRequest();
        // 255 chars total: "a" * 246 + "@test.com" = 246 + 9 = 255
        request.Email = new string('a', 246) + "@test.com";
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveValidationErrorFor(x => x.Email);
    }

    [Theory]
    [InlineData("user@example.com")]
    [InlineData("user.name@domain.org")]
    [InlineData("user+tag@sub.domain.co")]
    public void Validate_ValidEmailFormats_ShouldPass(string email)
    {
        var request = ValidRequest();
        request.Email = email;
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveValidationErrorFor(x => x.Email);
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
        request.Password = "Short1";
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Password);
    }

    [Fact]
    public void Validate_PasswordExactly8_ShouldPass()
    {
        var request = ValidRequest();
        request.Password = "Abcdef1x";
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveValidationErrorFor(x => x.Password);
    }

    [Fact]
    public void Validate_PasswordTooLong_ShouldFail()
    {
        var request = ValidRequest();
        request.Password = "A1" + new string('a', 127);
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Password);
    }

    [Fact]
    public void Validate_PasswordExactly128_ShouldPass()
    {
        var request = ValidRequest();
        request.Password = "A1" + new string('a', 126);
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveValidationErrorFor(x => x.Password);
    }

    [Fact]
    public void Validate_PasswordNoUppercase_ShouldFail()
    {
        var request = ValidRequest();
        request.Password = "alllower1";
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Password)
            .WithErrorMessage("Password must contain at least one uppercase letter.");
    }

    [Fact]
    public void Validate_PasswordNoLowercase_ShouldFail()
    {
        var request = ValidRequest();
        request.Password = "ALLUPPER1";
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Password)
            .WithErrorMessage("Password must contain at least one lowercase letter.");
    }

    [Fact]
    public void Validate_PasswordNoDigit_ShouldFail()
    {
        var request = ValidRequest();
        request.Password = "NoDigitsHere";
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Password)
            .WithErrorMessage("Password must contain at least one digit.");
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
    public void Validate_DisplayNameTooShort_ShouldFail()
    {
        var request = ValidRequest();
        request.DisplayName = "x";
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

    [Fact]
    public void Validate_DisplayNameExactly100_ShouldPass()
    {
        var request = ValidRequest();
        request.DisplayName = new string('x', 100);
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveValidationErrorFor(x => x.DisplayName);
    }

    private static CreateOwnerRequest ValidRequest() => new()
    {
        Email = "owner@example.com",
        Password = "SecureP1",
        DisplayName = "Jane Owner"
    };
}
