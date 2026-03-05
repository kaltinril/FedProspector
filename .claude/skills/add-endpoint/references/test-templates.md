# Test Code Templates

Test templates for steps 9-10 of the add-endpoint workflow. Read this file before creating test files.

## 9. Controller Tests

**Path:** `api/tests/FedProspector.Api.Tests/Controllers/{Entity}ControllerTests.cs`

```csharp
using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using FedProspector.Api.Controllers;
using FedProspector.Core.DTOs;
using FedProspector.Core.DTOs.{Entity}s;
using FedProspector.Core.Interfaces;
using FluentAssertions;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Moq;

namespace FedProspector.Api.Tests.Controllers;

public class {Entity}ControllerTests
{
    private readonly Mock<I{Entity}Service> _serviceMock = new();
    private readonly {Entity}Controller _controller;

    public {Entity}ControllerTests()
    {
        _controller = new {Entity}Controller(_serviceMock.Object);
        _controller.ControllerContext = new ControllerContext
        {
            HttpContext = new DefaultHttpContext()
        };
    }

    private static ClaimsPrincipal CreateUser(
        int userId = 1, string role = "user", bool isAdmin = false, int orgId = 1)
    {
        var claims = new List<Claim>
        {
            new(JwtRegisteredClaimNames.Sub, userId.ToString()),
            new(ClaimTypes.NameIdentifier, userId.ToString()),
            new(ClaimTypes.Role, role),
            new("is_admin", isAdmin.ToString().ToLower()),
            new("org_id", orgId.ToString())
        };
        return new ClaimsPrincipal(new ClaimsIdentity(claims, "TestAuth"));
    }

    private void SetAuthenticatedUser(int userId = 1, int orgId = 1)
    {
        _controller.ControllerContext.HttpContext.User = CreateUser(userId, orgId: orgId);
    }

    // --- Minimum 4 test cases per action ---

    [Fact]
    public async Task {ActionName}_NoOrgId_ReturnsUnauthorized()
    {
        var request = new {ActionName}Request();
        var result = await _controller.{ActionName}(request);
        result.Should().BeOfType<UnauthorizedResult>();
    }

    [Fact]
    public async Task {ActionName}_ValidRequest_ReturnsOk()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        var request = new {ActionName}Request();
        _serviceMock.Setup(s => s.{ActionName}Async(request, 10))
            .ReturnsAsync(new PagedResponse<{ActionName}Dto>());

        var result = await _controller.{ActionName}(request);
        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task {ActionName}_ValidRequest_CallsServiceWithCorrectParameters()
    {
        SetAuthenticatedUser(userId: 1, orgId: 10);
        var request = new {ActionName}Request();
        _serviceMock.Setup(s => s.{ActionName}Async(request, 10))
            .ReturnsAsync(new PagedResponse<{ActionName}Dto>());

        await _controller.{ActionName}(request);
        _serviceMock.Verify(s => s.{ActionName}Async(request, 10), Times.Once);
    }

    [Fact]
    public async Task {ActionName}_CallsServiceWithCorrectOrgId()
    {
        SetAuthenticatedUser(userId: 1, orgId: 42);
        var request = new {ActionName}Request();
        _serviceMock.Setup(s => s.{ActionName}Async(request, 42))
            .ReturnsAsync(new PagedResponse<{ActionName}Dto>());

        await _controller.{ActionName}(request);
        _serviceMock.Verify(s => s.{ActionName}Async(request, 42), Times.Once);
    }
}
```

**Test naming convention:** `{Method}_{Scenario}_{Expected}`

**FluentAssertions patterns:**
- `result.Should().BeOfType<OkObjectResult>()`
- `result.Should().BeOfType<UnauthorizedResult>()`
- `result.Should().BeOfType<NotFoundResult>()`
- `(result as OkObjectResult)!.Value.Should().Be(expected)`

**Reference:** `api/tests/FedProspector.Api.Tests/Controllers/OpportunitiesControllerTests.cs`

## 10. Validator Tests

**Path:** `api/tests/FedProspector.Core.Tests/Validators/{ActionName}RequestValidatorTests.cs`

```csharp
using FluentAssertions;
using FluentValidation.TestHelper;
using FedProspector.Core.DTOs.{Entity}s;
using FedProspector.Core.Validators;

namespace FedProspector.Core.Tests.Validators;

public class {ActionName}RequestValidatorTests
{
    private readonly {ActionName}RequestValidator _validator = new();

    [Fact]
    public void Validate_DefaultRequest_ShouldPass()
    {
        var request = new {ActionName}Request();
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveAnyValidationErrors();
    }

    [Fact]
    public void Validate_InvalidField_ShouldFail()
    {
        var request = new {ActionName}Request { SomeField = "invalid_value" };
        var result = _validator.TestValidate(request);
        result.ShouldHaveValidationErrorFor(x => x.SomeField);
    }

    [Fact]
    public void Validate_NullOptionalFields_ShouldPass()
    {
        var request = new {ActionName}Request
        {
            OptionalField = null
        };
        var result = _validator.TestValidate(request);
        result.ShouldNotHaveAnyValidationErrors();
    }
}
```

**Test patterns:**
- Instantiate validator in constructor (field initializer), not per-test
- Use `_validator.TestValidate(request)` from `FluentValidation.TestHelper`
- `result.ShouldNotHaveAnyValidationErrors()` for happy path
- `result.ShouldHaveValidationErrorFor(x => x.FieldName)` for failures
- Use `[Theory]` + `[InlineData]` for boundary testing

**Reference:** `api/tests/FedProspector.Core.Tests/Validators/OpportunitySearchRequestValidatorTests.cs`
