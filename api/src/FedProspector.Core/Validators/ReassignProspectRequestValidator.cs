using FluentValidation;
using FedProspector.Core.DTOs.Prospects;

namespace FedProspector.Core.Validators;

public class ReassignProspectRequestValidator : AbstractValidator<ReassignProspectRequest>
{
    public ReassignProspectRequestValidator()
    {
        RuleFor(x => x.NewAssignedTo).GreaterThan(0);
    }
}
