---
name: validate
description: Run all project tests in a forked context to verify nothing is broken. Returns pass/fail summary without polluting main context.
disable-model-invocation: true
context: fork
---

# Validate

Run all test suites and report a summary. This runs in a forked context so test output stays isolated.

## Steps

1. Run Python tests:
```bash
python -m pytest c:/git/fedProspect/fed_prospector/tests/ -v --tb=short
```

2. Run all C# tests (3 projects in parallel):
```bash
dotnet test c:/git/fedProspect/api/tests/FedProspector.Core.Tests/ --verbosity normal
dotnet test c:/git/fedProspect/api/tests/FedProspector.Api.Tests/ --verbosity normal
dotnet test c:/git/fedProspect/api/tests/FedProspector.Infrastructure.Tests/ --verbosity normal
```

3. Report summary: total passed, total failed, any errors. If all pass, say "All tests pass." If any fail, list the failing test names and brief error messages.
