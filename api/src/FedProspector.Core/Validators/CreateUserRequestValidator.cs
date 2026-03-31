using FluentValidation;
using FedProspector.Core.DTOs.Organizations;

namespace FedProspector.Core.Validators;

public class CreateUserRequestValidator : AbstractValidator<CreateUserRequest>
{
    private static readonly string[] AllowedOrgRoles = ["member", "admin"];

    public CreateUserRequestValidator()
    {
        RuleFor(x => x.Email)
            .NotEmpty()
            .EmailAddress()
            .MaximumLength(200);

        RuleFor(x => x.DisplayName)
            .NotEmpty()
            .MinimumLength(2)
            .MaximumLength(100);

        RuleFor(x => x.Password)
            .NotEmpty()
            .MinimumLength(8)
            .MaximumLength(128);

        RuleFor(x => x.OrgRole)
            .NotEmpty()
            .Must(role => AllowedOrgRoles.Contains(role))
            .WithMessage("OrgRole must be 'member' or 'admin'.");
    }
}
