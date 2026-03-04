using FluentValidation;
using FedProspector.Core.DTOs.Organizations;

namespace FedProspector.Core.Validators;

public class CreateOwnerRequestValidator : AbstractValidator<CreateOwnerRequest>
{
    public CreateOwnerRequestValidator()
    {
        RuleFor(x => x.Email)
            .NotEmpty()
            .EmailAddress()
            .MaximumLength(200);

        RuleFor(x => x.Password)
            .NotEmpty()
            .MinimumLength(8)
            .MaximumLength(100);

        RuleFor(x => x.DisplayName)
            .NotEmpty()
            .MaximumLength(100);
    }
}
