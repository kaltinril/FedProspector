using FluentValidation;
using FedProspector.Core.DTOs.Admin;

namespace FedProspector.Core.Validators;

public class UpdateUserRequestValidator : AbstractValidator<UpdateUserRequest>
{
    private static readonly string[] AllowedRoles = ["USER", "ADMIN"];

    public UpdateUserRequestValidator()
    {
        RuleFor(x => x.Role)
            .Must(r => AllowedRoles.Contains(r))
            .When(x => x.Role != null)
            .WithMessage("Role must be 'USER' or 'ADMIN'.");

        RuleFor(x => x)
            .Must(x => x.Role != null || x.IsAdmin.HasValue || x.IsActive.HasValue)
            .WithMessage("At least one field (Role, IsAdmin, IsActive) must be provided.");
    }
}
