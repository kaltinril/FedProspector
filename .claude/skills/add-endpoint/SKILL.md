---
name: add-endpoint
description: "Scaffold a new C# API endpoint following FedProspect patterns: DTO, Validator, Interface, Service, Controller action, and tests. Usage: /add-endpoint <EntityName> <ActionName> <HTTP method> <route>"
argument-hint: "<EntityName> <ActionName> <HTTP method> <route>"
disable-model-invocation: true
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

## Workflow

For each step, read the relevant template from `references/` before creating the file.

### Production Code (steps 1-8)

Read `references/templates.md` before creating these files.

1. **Request DTO** -- `api/src/FedProspector.Core/DTOs/{Entity}/{ActionName}Request.cs`
2. **Response DTO** -- `api/src/FedProspector.Core/DTOs/{Entity}/{ActionName}Dto.cs`
3. **Validator** -- `api/src/FedProspector.Core/Validators/{ActionName}RequestValidator.cs`
4. **Service Interface** -- `api/src/FedProspector.Core/Interfaces/I{Entity}Service.cs` (add method or create file)
5. **Service Implementation** -- `api/src/FedProspector.Infrastructure/Services/{Entity}Service.cs`
6. **Controller Action** -- `api/src/FedProspector.Api/Controllers/{Entity}Controller.cs` (add action or create file)
7. **DI Registration** -- `api/src/FedProspector.Api/Program.cs` (only for new services, keep alphabetical)
8. **AutoMapper mapping** -- only if 1:1 entity-to-DTO without transformation (usually skip)

### Tests (steps 9-10)

Read `references/test-templates.md` before creating these files.

9. **Controller Tests** -- `api/tests/FedProspector.Api.Tests/Controllers/{Entity}ControllerTests.cs`
   - Minimum 4 tests per action: NoAuth, HappyPath, VerifyServiceCall, VerifyOrgId
10. **Validator Tests** -- `api/tests/FedProspector.Core.Tests/Validators/{ActionName}RequestValidatorTests.cs`
    - Default passes, invalid fails, null optionals pass

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
| LEFT JOINs | `.DefaultIfEmpty()` in LINQ |
| Paged queries | Count before join for performance |
| Canonical example | `OpportunitiesController.cs` + `OpportunityService.cs` and their tests |

## Post-Scaffold

After creating all files:

```bash
# Build to verify compilation
dotnet build api/FedProspector.slnx

# Run relevant tests
dotnet test api/tests/FedProspector.Api.Tests/
dotnet test api/tests/FedProspector.Core.Tests/
```

## Quick Reference

See `references/checklist.md` for the condensed checklist version.
