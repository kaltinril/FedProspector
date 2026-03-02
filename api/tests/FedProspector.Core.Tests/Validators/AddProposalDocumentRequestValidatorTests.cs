using FluentAssertions;
using FluentValidation.TestHelper;
using FedProspector.Core.DTOs.Proposals;
using FedProspector.Core.Validators;

namespace FedProspector.Core.Tests.Validators;

public class AddProposalDocumentRequestValidatorTests
{
    private readonly AddProposalDocumentRequestValidator _validator = new();

    [Fact]
    public void Validate_ValidRequest_ShouldPass()
    {
        var request = new AddProposalDocumentRequest
        {
            FileName = "proposal.pdf",
            DocumentType = "TECHNICAL"
        };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveAnyValidationErrors();
    }

    [Theory]
    [InlineData("")]
    [InlineData(null)]
    public void Validate_EmptyFileName_ShouldFail(string? fileName)
    {
        var request = new AddProposalDocumentRequest { FileName = fileName!, DocumentType = "TECHNICAL" };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.FileName);
    }

    [Fact]
    public void Validate_FileNameTooLong_ShouldFail()
    {
        var request = new AddProposalDocumentRequest
        {
            FileName = new string('x', 256),
            DocumentType = "TECHNICAL"
        };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.FileName);
    }

    [Theory]
    [InlineData("")]
    [InlineData(null)]
    public void Validate_EmptyDocumentType_ShouldFail(string? docType)
    {
        var request = new AddProposalDocumentRequest { FileName = "file.pdf", DocumentType = docType! };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.DocumentType);
    }

    [Fact]
    public void Validate_DocumentTypeTooLong_ShouldFail()
    {
        var request = new AddProposalDocumentRequest
        {
            FileName = "file.pdf",
            DocumentType = new string('x', 51)
        };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.DocumentType);
    }
}
