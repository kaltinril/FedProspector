using FluentValidation;
using FedProspector.Core.DTOs.Prospects;

namespace FedProspector.Core.Validators;

public class UpdateProspectStatusRequestValidator : AbstractValidator<UpdateProspectStatusRequest>
{
    public UpdateProspectStatusRequestValidator()
    {
        RuleFor(x => x.NewStatus).NotEmpty();
    }
}
