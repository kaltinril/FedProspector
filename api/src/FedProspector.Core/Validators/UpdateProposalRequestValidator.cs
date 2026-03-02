using FluentValidation;
using FedProspector.Core.DTOs.Proposals;

namespace FedProspector.Core.Validators;

public class UpdateProposalRequestValidator : AbstractValidator<UpdateProposalRequest>
{
    private static readonly string[] ValidStatuses =
        ["DRAFT", "IN_REVIEW", "SUBMITTED", "UNDER_EVALUATION", "AWARDED", "NOT_AWARDED", "CANCELLED"];

    public UpdateProposalRequestValidator()
    {
        RuleFor(x => x.Status)
            .Must(s => ValidStatuses.Contains(s!))
            .When(x => !string.IsNullOrEmpty(x.Status))
            .WithMessage("Status must be one of: DRAFT, IN_REVIEW, SUBMITTED, UNDER_EVALUATION, AWARDED, NOT_AWARDED, CANCELLED");
    }
}
