using FluentValidation;
using FedProspector.Core.DTOs.SavedSearches;

namespace FedProspector.Core.Validators;

public class UpdateSavedSearchRequestValidator : AbstractValidator<UpdateSavedSearchRequest>
{
    public UpdateSavedSearchRequestValidator()
    {
        RuleFor(x => x.Name)
            .MaximumLength(100)
            .When(x => x.Name != null);

        RuleFor(x => x.Description)
            .MaximumLength(500)
            .When(x => x.Description != null);
    }
}
