using FluentValidation;
using FedProspector.Core.DTOs.Prospects;

namespace FedProspector.Core.Validators;

public class AddTeamMemberRequestValidator : AbstractValidator<AddTeamMemberRequest>
{
    private static readonly string[] ValidRoles = ["PRIME", "SUB", "MENTOR", "JV_PARTNER"];

    public AddTeamMemberRequestValidator()
    {
        RuleFor(x => x.Role)
            .NotEmpty()
            .Must(r => ValidRoles.Contains(r!))
            .WithMessage("Role must be one of: PRIME, SUB, MENTOR, JV_PARTNER");
    }
}
