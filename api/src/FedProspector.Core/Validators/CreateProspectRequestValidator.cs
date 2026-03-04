using FluentValidation;
using FedProspector.Core.DTOs.Prospects;

namespace FedProspector.Core.Validators;

public class CreateProspectRequestValidator : AbstractValidator<CreateProspectRequest>
{
    private static readonly string[] ValidPriorities = ["LOW", "MEDIUM", "HIGH", "CRITICAL"];

    public CreateProspectRequestValidator()
    {
        RuleFor(x => x.NoticeId).NotEmpty().MaximumLength(100);
        RuleFor(x => x.Priority)
            .Must(p => ValidPriorities.Contains(p!))
            .When(x => !string.IsNullOrEmpty(x.Priority))
            .WithMessage("Priority must be one of: LOW, MEDIUM, HIGH, CRITICAL");
        RuleFor(x => x.Notes).MaximumLength(10000).When(x => x.Notes != null);
    }
}
