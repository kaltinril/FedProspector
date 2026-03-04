---
name: add-endpoint
description: "Scaffold a new C# API endpoint following FedProspect patterns: DTO, Validator, Interface, Service, Controller action, and tests. Usage: /add-endpoint <EntityName> <ActionName> <HTTP method> <route>"
argument-hint: "<EntityName> <ActionName> <HTTP method> <route>"
disable-model-invocation: true
context: fork
agent: coder
---

# Add Endpoint

Scaffold a new C# ASP.NET Core API endpoint with all required files, following established FedProspect conventions.

## Arguments

Parse `$ARGUMENTS` as four positional values:

```
<EntityName> <ActionName> <HTTP method> <route>
```

Example: `Proposal Create POST /api/v1/proposals`

| Arg | Example | Used For |
|-----|---------|----------|
| EntityName | `Proposal` | Controller, Service, Interface, DTO folder naming |
| ActionName | `Create` | Request/Response DTO, Validator, service method naming |
| HTTP method | `POST` | `[Http{Method}]` attribute on controller action |
| route | `/api/v1/proposals` | `[Route(...)]` on controller class (base), action route segment if sub-route |

## Files to Create/Modify (in order)

### 1. Request DTO

**Path:** `api/src/FedProspector.Core/DTOs/{Entity}/{ActionName}Request.cs`

For search/list endpoints, inherit from `PagedRequest`. For create/update, use a plain class.

```csharp
using FedProspector.Core.DTOs;

namespace FedProspector.Core.DTOs.{Entity}s;  // note: pluralized folder namespace

// Search endpoint example (inherits PagedRequest):
public class {ActionName}Request : PagedRequest
{
    public string? FilterField { get; set; }
    public int? OptionalNumeric { get; set; }
}

// Create/Update endpoint example (plain class):
public class {ActionName}Request
{
    public string RequiredField { get; set; } = string.Empty;
    public string? OptionalField { get; set; }
}
```

**Reference:** `api/src/FedProspector.Core/DTOs/Opportunities/OpportunitySearchRequest.cs`

### 2. Response DTO

**Path:** `api/src/FedProspector.Core/DTOs/{Entity}/{ActionName}Dto.cs`

For paged results, this DTO is wrapped in `PagedResponse<T>` by the service. For single-item returns, use directly.

```csharp
namespace FedProspector.Core.DTOs.{Entity}s;

public class {ActionName}Dto
{
    public int Id { get; set; }
    public string Name { get; set; } = string.Empty;
    // Map only what the UI needs, not the full DB entity
}
```

### 3. Validator

**Path:** `api/src/FedProspector.Core/Validators/{ActionName}RequestValidator.cs`

```csharp
using FluentValidation;
using FedProspector.Core.DTOs.{Entity}s;

namespace FedProspector.Core.Validators;

public class {ActionName}RequestValidator : AbstractValidator<{ActionName}Request>
{
    public {ActionName}RequestValidator()
    {
        // For paged requests, always include:
        Include(new PagedRequestValidator());

        // Use .When() for conditional nullable rules:
        RuleFor(x => x.OptionalNumeric).GreaterThan(0).When(x => x.OptionalNumeric.HasValue);
        RuleFor(x => x.FilterField).MaximumLength(200).When(x => !string.IsNullOrEmpty(x.FilterField));

        // For required fields on create/update:
        RuleFor(x => x.RequiredField).NotEmpty().MaximumLength(500);
    }
}
```

**Key patterns:**
- Always `Include(new PagedRequestValidator())` for search validators
- Use `.When()` guards for nullable/optional fields
- String lengths: `.MaximumLength(N)` or `.Length(min, max)`

**Reference:** `api/src/FedProspector.Core/Validators/OpportunitySearchRequestValidator.cs`

### 4. Service Interface

**Path:** `api/src/FedProspector.Core/Interfaces/I{Entity}Service.cs`

Add a new method to the interface (or create the file if this is a new entity).

```csharp
using FedProspector.Core.DTOs;
using FedProspector.Core.DTOs.{Entity}s;

namespace FedProspector.Core.Interfaces;

public interface I{Entity}Service
{
    // Search (paged):
    Task<PagedResponse<{ActionName}Dto>> {ActionName}Async({ActionName}Request request, int organizationId);

    // Detail (single item, nullable):
    Task<{ActionName}Dto?> Get{ActionName}Async(int id, int organizationId);

    // Create (returns created item):
    Task<{ActionName}Dto> {ActionName}Async({ActionName}Request request, int organizationId);

    // Export:
    Task<string> ExportCsvAsync({ActionName}Request request, int organizationId);
}
```

**Conventions:**
- All methods are `async` (return `Task<T>`)
- Include `int organizationId` param for multi-tenancy on user-scoped tables
- Nullable return (`T?`) for single-item lookups (may return NotFound)

**Reference:** `api/src/FedProspector.Core/Interfaces/IOpportunityService.cs`

### 5. Service Implementation

**Path:** `api/src/FedProspector.Infrastructure/Services/{Entity}Service.cs`

```csharp
using FedProspector.Core.DTOs;
using FedProspector.Core.DTOs.{Entity}s;
using FedProspector.Core.Interfaces;
using FedProspector.Infrastructure.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;

namespace FedProspector.Infrastructure.Services;

public class {Entity}Service : I{Entity}Service
{
    private readonly FedProspectorDbContext _context;
    private readonly ILogger<{Entity}Service> _logger;

    public {Entity}Service(FedProspectorDbContext context, ILogger<{Entity}Service> logger)
    {
        _context = context;
        _logger = logger;
    }

    public async Task<PagedResponse<{ActionName}Dto>> {ActionName}Async(
        {ActionName}Request request, int organizationId)
    {
        var query = _context.{DbSetName}.AsNoTracking().AsQueryable();

        // Apply filters
        if (!string.IsNullOrWhiteSpace(request.FilterField))
            query = query.Where(x => x.SomeColumn == request.FilterField);

        // Count BEFORE joining (more efficient)
        var totalCount = await query.CountAsync();

        // LEFT JOIN to reference tables using DefaultIfEmpty()
        var enriched = from item in query
            join ref1 in _context.RefTable on item.FkCol equals ref1.PkCol into refJoin
            from ref1 in refJoin.DefaultIfEmpty()
            select new {ActionName}Dto
            {
                Id = item.Id,
                Name = item.Name,
                // Project to DTO inline, not AutoMapper
            };

        // Pagination
        var items = await enriched
            .Skip((request.Page - 1) * request.PageSize)
            .Take(request.PageSize)
            .ToListAsync();

        return new PagedResponse<{ActionName}Dto>
        {
            Items = items,
            TotalCount = totalCount,
            Page = request.Page,
            PageSize = request.PageSize
        };
    }
}
```

**Key patterns:**
- `.AsNoTracking()` on all read queries
- `.DefaultIfEmpty()` for LEFT JOINs
- Project to DTOs with `select new DtoType { ... }` (no AutoMapper for queries)
- Count before join for performance
- Filter by `organizationId` on user-scoped tables (e.g., prospects, proposals)

**Reference:** `api/src/FedProspector.Infrastructure/Services/OpportunityService.cs`

### 6. Controller Action

**Path:** `api/src/FedProspector.Api/Controllers/{Entity}Controller.cs`

Add an action to an existing controller, or create a new controller inheriting from `ApiControllerBase`.

```csharp
using FedProspector.Core.DTOs.{Entity}s;
using FedProspector.Core.Interfaces;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.RateLimiting;

namespace FedProspector.Api.Controllers;

[Route("api/v1/{entity-plural}")]
[Authorize]
[EnableRateLimiting("search")]
public class {Entity}Controller : ApiControllerBase
{
    private readonly I{Entity}Service _service;

    public {Entity}Controller(I{Entity}Service service)
    {
        _service = service;
    }

    [Http{Method}]           // or [Http{Method}("{routeParam}")]
    public async Task<IActionResult> {ActionName}([FromQuery] {ActionName}Request request)
    {
        var orgId = await ResolveOrganizationIdAsync();
        if (orgId == null) return Unauthorized();

        var result = await _service.{ActionName}Async(request, orgId.Value);
        return Ok(result);
    }
}
```

**Return type patterns:**
- Search/List: `return Ok(result);`
- Detail (nullable): `return result != null ? Ok(result) : NotFound();`
- Export CSV: `return File(bytes, "text/csv", "{entity}_export.csv");`
- Create: `return Ok(result);` or `return CreatedAtAction(...)`
- Delete: `return result ? NoContent() : NotFound();`

**Binding patterns:**
- GET with filters: `[FromQuery]`
- POST/PUT with body: `[FromBody]`
- Route params: method parameter matches `[Http{Method}("{paramName}")]`

**Reference:** `api/src/FedProspector.Api/Controllers/OpportunitiesController.cs`

### 7. DI Registration

**Path:** `api/src/FedProspector.Api/Program.cs` (lines 124-137)

Only add if this is a new service (not an additional action on an existing service).

```csharp
builder.Services.AddScoped<I{Entity}Service, {Entity}Service>();
```

Add to the block of `AddScoped` registrations (after line 137). Keep alphabetical order by service name within the block.

### 8. Mapping (if using AutoMapper)

**Path:** `api/src/FedProspector.Core/Mapping/MappingProfile.cs`

Most queries project directly with `select new DtoType { ... }` and skip AutoMapper. Only add a mapping profile entry if the DTO maps 1:1 from a DB entity without transformation.

## Tests to Create/Modify

### 9. Controller Tests

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

### 10. Validator Tests

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

## Conventions Summary

| Item | Convention |
|------|-----------|
| Controller class | `{Entity}Controller` (plural route: `api/v1/{entities}`) |
| Service interface | `I{Entity}Service` |
| Service class | `{Entity}Service` |
| Validator class | `{ActionName}RequestValidator` |
| DTO namespace | `FedProspector.Core.DTOs.{Entities}` (pluralized) |
| Test naming | `{Method}_{Scenario}_{Expected}` |
| Org isolation | `ResolveOrganizationIdAsync()` + null check in every controller action |
| Read queries | `.AsNoTracking()` always |
| Canonical example | `OpportunitiesController.cs` + `OpportunityService.cs` and their tests |

## Post-Scaffold

After creating all files:

```bash
# Build to verify compilation
dotnet build c:/git/fedProspect/api/FedProspector.slnx

# Run relevant tests
dotnet test c:/git/fedProspect/api/tests/FedProspector.Api.Tests/
dotnet test c:/git/fedProspect/api/tests/FedProspector.Core.Tests/
```

Update test counts in `CLAUDE.md` and `MEMORY.md` if new tests were added.

## Quick Reference

See `references/endpoint-checklist.md` for the condensed checklist version.
