---
name: run-tests
description: "Run project test suites: Python pytest and/or C# xUnit. Also acts as a validation check — use when you need to verify code changes, check for regressions, confirm nothing is broken, or run specific test filters. Supports all, python, csharp, core, api, infra. Usage: /run-tests [suite] [filter]"
argument-hint: "[all|python|csharp|core|api|infra] [filter]"
disable-model-invocation: true
---

# Run Tests

Run one or more of the 4 test suites. Python and C# suites are independent — run them in parallel when running `all`.

## Arguments

- `$ARGUMENTS` = `[suite] [optional filter]`
- Suite: `all` (default), `python`, `csharp` (all 3 C#), `core`, `api`, `infra`
- Filter: passed as `-k <filter>` (pytest) or `--filter <filter>` (dotnet)

## Commands

### Python
```bash
python -m pytest fed_prospector/tests/ -v --tb=short
```
With filter: `python -m pytest fed_prospector/tests/ -v --tb=short -k "<filter>"`

### C# Core
```bash
dotnet test api/tests/FedProspector.Core.Tests/ --verbosity normal
```

### C# Api
```bash
dotnet test api/tests/FedProspector.Api.Tests/ --verbosity normal
```

### C# Infrastructure
```bash
dotnet test api/tests/FedProspector.Infrastructure.Tests/ --verbosity normal
```

With filter: add `--filter "FullyQualifiedName~<filter>"`

## Parallelism

When running `all` or `csharp`, launch independent suites in parallel using multiple Bash tool calls in a single message. Python is independent of all C# suites. The 3 C# projects can also run in parallel.

## On Failure

Show failing test names and relevant output. Do NOT attempt to fix tests unless the user explicitly asks.
