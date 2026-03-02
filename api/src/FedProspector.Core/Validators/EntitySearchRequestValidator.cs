using FluentValidation;
using FedProspector.Core.DTOs.Entities;

namespace FedProspector.Core.Validators;

public class EntitySearchRequestValidator : AbstractValidator<EntitySearchRequest>
{
    public EntitySearchRequestValidator()
    {
        Include(new PagedRequestValidator());
        RuleFor(x => x.Uei).Length(12).When(x => !string.IsNullOrEmpty(x.Uei));
        RuleFor(x => x.RegistrationStatus).Length(1).When(x => !string.IsNullOrEmpty(x.RegistrationStatus));
        RuleFor(x => x.Naics).Length(2, 6).When(x => !string.IsNullOrEmpty(x.Naics));
    }
}
