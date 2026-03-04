using FluentValidation;
using FedProspector.Core.DTOs.Prospects;

namespace FedProspector.Core.Validators;

public class CreateProspectNoteRequestValidator : AbstractValidator<CreateProspectNoteRequest>
{
    private static readonly string[] ValidNoteTypes =
        ["COMMENT", "ASSIGNMENT", "DECISION", "REVIEW", "MEETING", "PHONE_CALL", "EMAIL"];

    public CreateProspectNoteRequestValidator()
    {
        RuleFor(x => x.NoteType)
            .NotEmpty()
            .Must(t => ValidNoteTypes.Contains(t!))
            .WithMessage("NoteType must be one of: COMMENT, ASSIGNMENT, DECISION, REVIEW, MEETING, PHONE_CALL, EMAIL");
        RuleFor(x => x.NoteText).NotEmpty().MaximumLength(10000);
    }
}
