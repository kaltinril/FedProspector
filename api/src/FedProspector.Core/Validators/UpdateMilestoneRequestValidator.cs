using FluentValidation;
using FedProspector.Core.DTOs.Proposals;

namespace FedProspector.Core.Validators;

public class UpdateMilestoneRequestValidator : AbstractValidator<UpdateMilestoneRequest>
{
    private static readonly string[] ValidStatuses = ["PENDING", "IN_PROGRESS", "COMPLETED", "SKIPPED"];

    public UpdateMilestoneRequestValidator()
    {
        RuleFor(x => x.Status)
            .Must(s => ValidStatuses.Contains(s!))
            .When(x => !string.IsNullOrEmpty(x.Status))
            .WithMessage("Status must be one of: PENDING, IN_PROGRESS, COMPLETED, SKIPPED");
        RuleFor(x => x.Notes).MaximumLength(10000).When(x => x.Notes != null);
    }
}
