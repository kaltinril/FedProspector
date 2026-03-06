using FluentValidation;
using FedProspector.Core.DTOs.Awards;

namespace FedProspector.Core.Validators;

public class AwardSearchRequestValidator : AbstractValidator<AwardSearchRequest>
{
    public AwardSearchRequestValidator()
    {
        Include(new PagedRequestValidator());
        RuleFor(x => x.Piid).MaximumLength(50).When(x => !string.IsNullOrEmpty(x.Piid));
        RuleFor(x => x.MinValue).GreaterThanOrEqualTo(0).When(x => x.MinValue.HasValue);
        RuleFor(x => x.MaxValue).GreaterThanOrEqualTo(x => x.MinValue ?? 0)
            .When(x => x.MaxValue.HasValue && x.MinValue.HasValue);
        RuleFor(x => x.DateTo).GreaterThanOrEqualTo(x => x.DateFrom!.Value)
            .When(x => x.DateTo.HasValue && x.DateFrom.HasValue);
        RuleFor(x => x.VendorUei).Length(12).When(x => !string.IsNullOrEmpty(x.VendorUei));
    }
}
