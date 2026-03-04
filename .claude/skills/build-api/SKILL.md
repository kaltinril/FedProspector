---
name: build-api
description: "Build the C# ASP.NET Core Web API solution. Restores NuGet packages and builds all projects. Usage: /build-api [Release|Debug]"
argument-hint: "[Release|Debug]"
disable-model-invocation: true
---

# Build API

Build the C# solution including Api, Core, Infrastructure, and all test projects.

## Command

```bash
dotnet build c:/git/fedProspect/api/FedProspector.slnx -c <config>
```

- `$ARGUMENTS` = configuration name (default: `Debug`)
- Valid values: `Debug`, `Release`

## If Build Fails with Package Restore Errors

```bash
dotnet restore c:/git/fedProspect/api/FedProspector.slnx
```

Then retry the build.

## Project Structure

| Project | Path |
|---------|------|
| Api (entry point) | `api/src/FedProspector.Api/` |
| Core (DTOs, interfaces, validators) | `api/src/FedProspector.Core/` |
| Infrastructure (services, DbContext) | `api/src/FedProspector.Infrastructure/` |
| Core Tests | `api/tests/FedProspector.Core.Tests/` |
| Api Tests | `api/tests/FedProspector.Api.Tests/` |
| Infrastructure Tests | `api/tests/FedProspector.Infrastructure.Tests/` |

## After Build

Report: success/failure, warning count, error details. Do not run tests unless asked.
