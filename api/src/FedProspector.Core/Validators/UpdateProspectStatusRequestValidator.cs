using FluentValidation;
using FedProspector.Core.DTOs.Prospects;

namespace FedProspector.Core.Validators;

public class UpdateProspectStatusRequestValidator : AbstractValidator<UpdateProspectStatusRequest>
{
    private static readonly HashSet<string> ValidStatuses = new(StringComparer.OrdinalIgnoreCase)
    {
        "NEW", "REVIEWING", "PURSUING", "BID_SUBMITTED",
        "WON", "LOST", "DECLINED", "NO_BID"
    };

    public UpdateProspectStatusRequestValidator()
    {
        RuleFor(x => x.NewStatus)
            .NotEmpty()
            .Must(s => ValidStatuses.Contains(s))
            .WithMessage("Invalid status. Valid values: " + string.Join(", ", ValidStatuses));
    }
}
