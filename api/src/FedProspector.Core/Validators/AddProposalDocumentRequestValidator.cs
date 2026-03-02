using FluentValidation;
using FedProspector.Core.DTOs.Proposals;

namespace FedProspector.Core.Validators;

public class AddProposalDocumentRequestValidator : AbstractValidator<AddProposalDocumentRequest>
{
    public AddProposalDocumentRequestValidator()
    {
        RuleFor(x => x.FileName).NotEmpty().MaximumLength(255);
        RuleFor(x => x.DocumentType).NotEmpty().MaximumLength(50);
    }
}
