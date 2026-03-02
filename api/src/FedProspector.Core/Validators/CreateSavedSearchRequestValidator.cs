using FluentValidation;
using FedProspector.Core.DTOs.SavedSearches;

namespace FedProspector.Core.Validators;

public class CreateSavedSearchRequestValidator : AbstractValidator<CreateSavedSearchRequest>
{
    public CreateSavedSearchRequestValidator()
    {
        RuleFor(x => x.SearchName).NotEmpty().MaximumLength(100);
        RuleFor(x => x.FilterCriteria).NotNull();
    }
}
