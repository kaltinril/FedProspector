using FluentAssertions;
using FluentValidation.TestHelper;
using FedProspector.Core.DTOs.SavedSearches;
using FedProspector.Core.Validators;

namespace FedProspector.Core.Tests.Validators;

public class CreateSavedSearchRequestValidatorTests
{
    private readonly CreateSavedSearchRequestValidator _validator = new();

    [Fact]
    public void Validate_ValidRequest_ShouldPass()
    {
        var request = new CreateSavedSearchRequest
        {
            SearchName = "My Search",
            FilterCriteria = new SavedSearchFilterCriteria()
        };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveAnyValidationErrors();
    }

    [Theory]
    [InlineData("")]
    [InlineData(null)]
    public void Validate_EmptySearchName_ShouldFail(string? name)
    {
        var request = new CreateSavedSearchRequest
        {
            SearchName = name!,
            FilterCriteria = new SavedSearchFilterCriteria()
        };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.SearchName);
    }

    [Fact]
    public void Validate_SearchNameTooLong_ShouldFail()
    {
        var request = new CreateSavedSearchRequest
        {
            SearchName = new string('x', 101),
            FilterCriteria = new SavedSearchFilterCriteria()
        };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.SearchName);
    }

    [Fact]
    public void Validate_SearchNameExactly100_ShouldPass()
    {
        var request = new CreateSavedSearchRequest
        {
            SearchName = new string('x', 100),
            FilterCriteria = new SavedSearchFilterCriteria()
        };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveValidationErrorFor(x => x.SearchName);
    }

    [Fact]
    public void Validate_NullFilterCriteria_ShouldFail()
    {
        var request = new CreateSavedSearchRequest
        {
            SearchName = "Test",
            FilterCriteria = null!
        };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.FilterCriteria);
    }
}
