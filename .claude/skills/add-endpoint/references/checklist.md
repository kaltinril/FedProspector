# Endpoint Checklist

Quick reference for adding a new API endpoint. See SKILL.md for detailed patterns.

## Files (in order)

- [ ] Request DTO: `api/src/FedProspector.Core/DTOs/{Entity}/{ActionName}Request.cs`
- [ ] Response DTO: `api/src/FedProspector.Core/DTOs/{Entity}/{ActionName}Dto.cs`
- [ ] Validator: `api/src/FedProspector.Core/Validators/{ActionName}RequestValidator.cs`
- [ ] Interface: `api/src/FedProspector.Core/Interfaces/I{Entity}Service.cs`
- [ ] Service: `api/src/FedProspector.Infrastructure/Services/{Entity}Service.cs`
- [ ] Controller: `api/src/FedProspector.Api/Controllers/{Entity}Controller.cs`
- [ ] DI Registration: `api/src/FedProspector.Api/Program.cs` (if new service)
- [ ] Mapping: `api/src/FedProspector.Core/Mapping/MappingProfile.cs` (if AutoMapper)
- [ ] Controller Tests: `api/tests/FedProspector.Api.Tests/Controllers/{Entity}ControllerTests.cs`
- [ ] Validator Tests: `api/tests/FedProspector.Core.Tests/Validators/{ActionName}RequestValidatorTests.cs`

## Must-Have Patterns

- ResolveOrganizationIdAsync() + null check in every controller action
- .AsNoTracking() on all read queries
- PagedRequestValidator included for paged search validators
- .When() guards on nullable/optional validator rules
- .DefaultIfEmpty() for LEFT JOINs in LINQ
- Count before join for paged queries
- 4 test cases minimum: NoAuth, HappyPath, VerifyServiceCall, VerifyOrgId

## Canonical References

- Controller: `api/src/FedProspector.Api/Controllers/OpportunitiesController.cs`
- Service: `api/src/FedProspector.Infrastructure/Services/OpportunityService.cs`
- Interface: `api/src/FedProspector.Core/Interfaces/IOpportunityService.cs`
- Validator: `api/src/FedProspector.Core/Validators/OpportunitySearchRequestValidator.cs`
- Controller Tests: `api/tests/FedProspector.Api.Tests/Controllers/OpportunitiesControllerTests.cs`
- Validator Tests: `api/tests/FedProspector.Core.Tests/Validators/OpportunitySearchRequestValidatorTests.cs`

## DI Registration Location

`api/src/FedProspector.Api/Program.cs` (AddScoped block)

## Build & Test

```bash
dotnet build api/FedProspector.slnx
dotnet test api/tests/FedProspector.Api.Tests/
dotnet test api/tests/FedProspector.Core.Tests/
```
