using FluentAssertions;
using FluentValidation.TestHelper;
using FedProspector.Core.DTOs.Prospects;
using FedProspector.Core.Validators;

namespace FedProspector.Core.Tests.Validators;

public class CreateProspectNoteRequestValidatorTests
{
    private readonly CreateProspectNoteRequestValidator _validator = new();

    [Fact]
    public void Validate_ValidRequest_ShouldPass()
    {
        var request = new CreateProspectNoteRequest { NoteType = "COMMENT", NoteText = "A note" };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveAnyValidationErrors();
    }

    [Theory]
    [InlineData("COMMENT")]
    [InlineData("ASSIGNMENT")]
    [InlineData("DECISION")]
    [InlineData("REVIEW")]
    [InlineData("MEETING")]
    [InlineData("PHONE_CALL")]
    [InlineData("EMAIL")]
    public void Validate_ValidNoteType_ShouldPass(string noteType)
    {
        var request = new CreateProspectNoteRequest { NoteType = noteType, NoteText = "Text" };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveValidationErrorFor(x => x.NoteType);
    }

    [Fact]
    public void Validate_InvalidNoteType_ShouldFail()
    {
        var request = new CreateProspectNoteRequest { NoteType = "INVALID", NoteText = "Text" };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.NoteType);
    }

    [Theory]
    [InlineData("")]
    [InlineData(null)]
    public void Validate_EmptyNoteType_ShouldFail(string? noteType)
    {
        var request = new CreateProspectNoteRequest { NoteType = noteType!, NoteText = "Text" };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.NoteType);
    }

    [Theory]
    [InlineData("")]
    [InlineData(null)]
    public void Validate_EmptyNoteText_ShouldFail(string? noteText)
    {
        var request = new CreateProspectNoteRequest { NoteType = "COMMENT", NoteText = noteText! };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.NoteText);
    }
}
