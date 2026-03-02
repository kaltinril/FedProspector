using FluentValidation;
using FedProspector.Core.DTOs.Proposals;

namespace FedProspector.Core.Validators;

public class CreateMilestoneRequestValidator : AbstractValidator<CreateMilestoneRequest>
{
    public CreateMilestoneRequestValidator()
    {
        RuleFor(x => x.Title).NotEmpty().MaximumLength(100);
        RuleFor(x => x.DueDate).NotEmpty();
    }
}
