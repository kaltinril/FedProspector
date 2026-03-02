using FluentAssertions;
using FluentValidation.TestHelper;
using FedProspector.Core.DTOs.Prospects;
using FedProspector.Core.Validators;

namespace FedProspector.Core.Tests.Validators;

public class CreateProspectRequestValidatorTests
{
    private readonly CreateProspectRequestValidator _validator = new();

    [Fact]
    public void Validate_ValidRequest_ShouldPass()
    {
        var request = new CreateProspectRequest { NoticeId = "ABC123", Priority = "HIGH" };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveAnyValidationErrors();
    }

    [Theory]
    [InlineData("")]
    [InlineData(null)]
    public void Validate_EmptyNoticeId_ShouldFail(string? noticeId)
    {
        var request = new CreateProspectRequest { NoticeId = noticeId! };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.NoticeId);
    }

    [Fact]
    public void Validate_NoticeIdTooLong_ShouldFail()
    {
        var request = new CreateProspectRequest { NoticeId = new string('x', 101) };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.NoticeId);
    }

    [Theory]
    [InlineData("LOW")]
    [InlineData("MEDIUM")]
    [InlineData("HIGH")]
    [InlineData("CRITICAL")]
    public void Validate_ValidPriority_ShouldPass(string priority)
    {
        var request = new CreateProspectRequest { NoticeId = "ABC", Priority = priority };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveValidationErrorFor(x => x.Priority);
    }

    [Fact]
    public void Validate_InvalidPriority_ShouldFail()
    {
        var request = new CreateProspectRequest { NoticeId = "ABC", Priority = "URGENT" };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Priority);
    }

    [Fact]
    public void Validate_NullPriority_ShouldPass()
    {
        var request = new CreateProspectRequest { NoticeId = "ABC", Priority = null };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveValidationErrorFor(x => x.Priority);
    }
}
