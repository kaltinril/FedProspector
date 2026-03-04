using FluentAssertions;
using FluentValidation.TestHelper;
using FedProspector.Core.DTOs.Proposals;
using FedProspector.Core.Validators;

namespace FedProspector.Core.Tests.Validators;

public class CreateMilestoneRequestValidatorTests
{
    private readonly CreateMilestoneRequestValidator _validator = new();

    [Fact]
    public void Validate_ValidRequest_ShouldPass()
    {
        var request = new CreateMilestoneRequest
        {
            Title = "Review Draft",
            DueDate = DateTime.UtcNow.AddDays(7)
        };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveAnyValidationErrors();
    }

    [Theory]
    [InlineData("")]
    [InlineData(null)]
    public void Validate_EmptyTitle_ShouldFail(string? title)
    {
        var request = new CreateMilestoneRequest
        {
            Title = title!,
            DueDate = DateTime.UtcNow.AddDays(7)
        };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Title);
    }

    [Fact]
    public void Validate_TitleExactly100_ShouldPass()
    {
        var request = new CreateMilestoneRequest
        {
            Title = new string('x', 100),
            DueDate = DateTime.UtcNow.AddDays(7)
        };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveValidationErrorFor(x => x.Title);
    }

    [Fact]
    public void Validate_TitleTooLong_ShouldFail()
    {
        var request = new CreateMilestoneRequest
        {
            Title = new string('x', 101),
            DueDate = DateTime.UtcNow.AddDays(7)
        };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Title);
    }

    [Fact]
    public void Validate_DefaultDueDate_ShouldFail()
    {
        var request = new CreateMilestoneRequest
        {
            Title = "Test Milestone",
            DueDate = default
        };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.DueDate);
    }
}
