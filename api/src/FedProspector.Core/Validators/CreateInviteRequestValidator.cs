using FluentValidation;
using FedProspector.Core.DTOs.Organizations;

namespace FedProspector.Core.Validators;

public class CreateInviteRequestValidator : AbstractValidator<CreateInviteRequest>
{
    private static readonly string[] AllowedOrgRoles = ["member", "admin"];

    public CreateInviteRequestValidator()
    {
        RuleFor(x => x.Email)
            .NotEmpty()
            .EmailAddress()
            .MaximumLength(200);

        RuleFor(x => x.OrgRole)
            .NotEmpty()
            .Must(role => AllowedOrgRoles.Contains(role))
            .WithMessage("OrgRole must be 'member' or 'admin'.");
    }
}
