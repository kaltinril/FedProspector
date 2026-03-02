using FluentValidation;
using FedProspector.Core.DTOs.Notifications;

namespace FedProspector.Core.Validators;

public class NotificationListRequestValidator : AbstractValidator<NotificationListRequest>
{
    private static readonly string[] ValidTypes =
    [
        "DEADLINE_APPROACHING",
        "PROSPECT_ASSIGNED",
        "STATUS_CHANGED",
        "MILESTONE_DUE",
        "SEARCH_RESULTS",
        "ETL_COMPLETE"
    ];

    public NotificationListRequestValidator()
    {
        Include(new PagedRequestValidator());
        RuleFor(x => x.Type)
            .Must(t => ValidTypes.Contains(t!))
            .When(x => !string.IsNullOrEmpty(x.Type))
            .WithMessage($"Type must be one of: {string.Join(", ", ValidTypes)}");
    }
}
