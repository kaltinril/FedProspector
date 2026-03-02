using FluentValidation;
using FedProspector.Core.DTOs.Opportunities;

namespace FedProspector.Core.Validators;

public class TargetOpportunitySearchRequestValidator : AbstractValidator<TargetOpportunitySearchRequest>
{
    public TargetOpportunitySearchRequestValidator()
    {
        Include(new PagedRequestValidator());
        RuleFor(x => x.MinValue).GreaterThanOrEqualTo(0).When(x => x.MinValue.HasValue);
        RuleFor(x => x.MaxValue).GreaterThanOrEqualTo(x => x.MinValue ?? 0)
            .When(x => x.MaxValue.HasValue && x.MinValue.HasValue);
    }
}
