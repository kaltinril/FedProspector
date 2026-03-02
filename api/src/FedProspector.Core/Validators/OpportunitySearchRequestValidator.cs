using FluentValidation;
using FedProspector.Core.DTOs.Opportunities;

namespace FedProspector.Core.Validators;

public class OpportunitySearchRequestValidator : AbstractValidator<OpportunitySearchRequest>
{
    public OpportunitySearchRequestValidator()
    {
        Include(new PagedRequestValidator());
        RuleFor(x => x.DaysOut).GreaterThan(0).When(x => x.DaysOut.HasValue);
        RuleFor(x => x.Naics).Length(2, 6).When(x => !string.IsNullOrEmpty(x.Naics));
        RuleFor(x => x.State).Length(2).When(x => !string.IsNullOrEmpty(x.State));
    }
}
