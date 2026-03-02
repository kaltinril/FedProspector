using FluentValidation;
using FedProspector.Core.DTOs;

namespace FedProspector.Core.Validators;

public class UpdateProfileRequestValidator : AbstractValidator<UpdateProfileRequest>
{
    public UpdateProfileRequestValidator()
    {
        RuleFor(x => x.DisplayName)
            .MinimumLength(1)
            .MaximumLength(100)
            .When(x => x.DisplayName is not null);

        RuleFor(x => x.Email)
            .EmailAddress()
            .MaximumLength(200)
            .When(x => x.Email is not null);
    }
}
