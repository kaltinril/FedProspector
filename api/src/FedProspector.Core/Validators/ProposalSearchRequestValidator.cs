using FluentValidation;
using FedProspector.Core.DTOs.Proposals;

namespace FedProspector.Core.Validators;

public class ProposalSearchRequestValidator : AbstractValidator<ProposalSearchRequest>
{
    private static readonly string[] ValidStatuses =
        ["DRAFT", "IN_REVIEW", "SUBMITTED", "UNDER_EVALUATION", "AWARDED", "NOT_AWARDED", "CANCELLED"];

    public ProposalSearchRequestValidator()
    {
        RuleFor(x => x.Status)
            .Must(s => ValidStatuses.Contains(s!))
            .When(x => !string.IsNullOrEmpty(x.Status))
            .WithMessage("Status must be one of: DRAFT, IN_REVIEW, SUBMITTED, UNDER_EVALUATION, AWARDED, NOT_AWARDED, CANCELLED");

        RuleFor(x => x.ProspectId)
            .GreaterThan(0)
            .When(x => x.ProspectId.HasValue);
    }
}
