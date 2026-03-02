using FluentAssertions;
using FluentValidation.TestHelper;
using FedProspector.Core.DTOs.Notifications;
using FedProspector.Core.Validators;

namespace FedProspector.Core.Tests.Validators;

public class NotificationListRequestValidatorTests
{
    private readonly NotificationListRequestValidator _validator = new();

    [Fact]
    public void Validate_DefaultRequest_ShouldPass()
    {
        var request = new NotificationListRequest();
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveAnyValidationErrors();
    }

    [Theory]
    [InlineData("DEADLINE_APPROACHING")]
    [InlineData("PROSPECT_ASSIGNED")]
    [InlineData("STATUS_CHANGED")]
    [InlineData("MILESTONE_DUE")]
    [InlineData("SEARCH_RESULTS")]
    [InlineData("ETL_COMPLETE")]
    public void Validate_ValidType_ShouldPass(string type)
    {
        var request = new NotificationListRequest { Type = type };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveValidationErrorFor(x => x.Type);
    }

    [Fact]
    public void Validate_InvalidType_ShouldFail()
    {
        var request = new NotificationListRequest { Type = "INVALID_TYPE" };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.Type);
    }

    [Fact]
    public void Validate_NullType_ShouldPass()
    {
        var request = new NotificationListRequest { Type = null };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveValidationErrorFor(x => x.Type);
    }

    [Fact]
    public void Validate_EmptyType_ShouldPass()
    {
        // Empty string is treated as "not provided" by the When condition
        var request = new NotificationListRequest { Type = "" };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveValidationErrorFor(x => x.Type);
    }
}
