using FluentAssertions;
using FluentValidation.TestHelper;
using FedProspector.Core.DTOs.SavedSearches;
using FedProspector.Core.Validators;

namespace FedProspector.Core.Tests.Validators;

public class UpdateSavedSearchRequestValidatorTests
{
    private readonly UpdateSavedSearchRequestValidator _validator = new();

    [Fact]
    public void Validate_ValidRequest_ShouldPass()
    {
        var request = new UpdateSavedSearchRequest
        {
            Name = "Updated Search",
            Description = "A revised description"
        };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveAnyValidationErrors();
    }

    [Fact]
    public void Validate_AllNullFields_ShouldPass()
    {
        var request = new UpdateSavedSearchRequest();
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveAnyValidationErrors();
    }

    [Fact]
    public void Validate_NameExactly100_ShouldPass()
    {
        var request = new UpdateSavedSearchRequest
        {
            Name = new string('x', 100)
        };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveValidationErrorFor(x => x.Name);
    }

    [Fact]
    public void Validate_NameTooLong_ShouldFail()
    {
        var request = new UpdateSavedSearchRequest
        {
            Name = new string('x', 101)
        };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Name);
    }

    [Fact]
    public void Validate_DescriptionExactly500_ShouldPass()
    {
        var request = new UpdateSavedSearchRequest
        {
            Description = new string('y', 500)
        };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveValidationErrorFor(x => x.Description);
    }

    [Fact]
    public void Validate_DescriptionTooLong_ShouldFail()
    {
        var request = new UpdateSavedSearchRequest
        {
            Description = new string('y', 501)
        };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Description);
    }
}
