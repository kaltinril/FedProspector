using FluentValidation;
using FedProspector.Core.DTOs.Subawards;

namespace FedProspector.Core.Validators;

public class TeamingPartnerSearchRequestValidator : AbstractValidator<TeamingPartnerSearchRequest>
{
    public TeamingPartnerSearchRequestValidator()
    {
        Include(new PagedRequestValidator());
        RuleFor(x => x.MinSubawards).GreaterThanOrEqualTo(1);
    }
}
