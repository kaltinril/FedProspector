using FluentAssertions;
using FluentValidation.TestHelper;
using FedProspector.Core.DTOs.Organizations;
using FedProspector.Core.Validators;

namespace FedProspector.Core.Tests.Validators;

public class CreateOrganizationRequestValidatorTests
{
    private readonly CreateOrganizationRequestValidator _validator = new();

    [Fact]
    public void Validate_ValidRequest_ShouldPass()
    {
        var request = new CreateOrganizationRequest
        {
            Name = "Acme Corp",
            Slug = "acme-corp"
        };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveAnyValidationErrors();
    }

    // --- Name rules ---

    [Theory]
    [InlineData("")]
    [InlineData(null)]
    public void Validate_EmptyName_ShouldFail(string? name)
    {
        var request = ValidRequest();
        request.Name = name!;
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Name);
    }

    [Fact]
    public void Validate_NameTooLong_ShouldFail()
    {
        var request = ValidRequest();
        request.Name = new string('x', 201);
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Name);
    }

    [Fact]
    public void Validate_NameExactly200_ShouldPass()
    {
        var request = ValidRequest();
        request.Name = new string('x', 200);
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveValidationErrorFor(x => x.Name);
    }

    // --- Slug rules ---

    [Theory]
    [InlineData("")]
    [InlineData(null)]
    public void Validate_EmptySlug_ShouldFail(string? slug)
    {
        var request = ValidRequest();
        request.Slug = slug!;
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Slug);
    }

    [Fact]
    public void Validate_SlugTooLong_ShouldFail()
    {
        var request = ValidRequest();
        request.Slug = new string('a', 101);
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Slug);
    }

    [Fact]
    public void Validate_SlugExactly100_ShouldPass()
    {
        var request = ValidRequest();
        request.Slug = new string('a', 100);
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveValidationErrorFor(x => x.Slug);
    }

    [Theory]
    [InlineData("valid-slug")]
    [InlineData("abc123")]
    [InlineData("my-org-2026")]
    [InlineData("a")]
    public void Validate_SlugValidFormat_ShouldPass(string slug)
    {
        var request = ValidRequest();
        request.Slug = slug;
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveValidationErrorFor(x => x.Slug);
    }

    [Theory]
    [InlineData("UPPERCASE")]
    [InlineData("Mixed-Case")]
    [InlineData("has spaces")]
    [InlineData("has_underscore")]
    [InlineData("special@char")]
    [InlineData("dot.slug")]
    [InlineData("slash/slug")]
    public void Validate_SlugInvalidFormat_ShouldFail(string slug)
    {
        var request = ValidRequest();
        request.Slug = slug;
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Slug);
    }

    [Fact]
    public void Validate_SlugInvalidFormat_ShouldHaveCustomMessage()
    {
        var request = ValidRequest();
        request.Slug = "INVALID_SLUG";
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Slug)
            .WithErrorMessage("Slug must contain only lowercase letters, numbers, and hyphens.");
    }

    private static CreateOrganizationRequest ValidRequest() => new()
    {
        Name = "Acme Corp",
        Slug = "acme-corp"
    };
}
