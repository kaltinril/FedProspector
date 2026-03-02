using FluentValidation;
using FedProspector.Core.DTOs.Prospects;

namespace FedProspector.Core.Validators;

public class ProspectSearchRequestValidator : AbstractValidator<ProspectSearchRequest>
{
    public ProspectSearchRequestValidator()
    {
        Include(new PagedRequestValidator());
        RuleFor(x => x.Status).MaximumLength(50).When(x => !string.IsNullOrEmpty(x.Status));
        RuleFor(x => x.Priority).MaximumLength(20).When(x => !string.IsNullOrEmpty(x.Priority));
        RuleFor(x => x.Naics).Length(2, 6).When(x => !string.IsNullOrEmpty(x.Naics));
        RuleFor(x => x.SetAside).MaximumLength(50).When(x => !string.IsNullOrEmpty(x.SetAside));
    }
}
