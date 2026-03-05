---
name: scaffold-react-page
description: "[DRAFT — revisit when Phase 20 starts] Scaffold a new React page following FedProspect UI patterns: page component, API module, TanStack Query hooks, route registration, and MUI layout. Usage: /scaffold-react-page <PageName> <api-entity>"
argument-hint: "<PageName> <api-entity>"
disable-model-invocation: true
---

**Arguments**: `$ARGUMENTS` = `<PageName> <api-entity>` (e.g., `OpportunitySearch opportunities`)

**Pre-check**: If `ui/src/` doesn't exist or Phase 20 foundation isn't in place, warn the user and stop.

## Files to Create

Read `references/templates.md` for code templates before creating files.

1. **Page Component** — `ui/src/pages/{PageName}/{PageName}Page.tsx`
2. **API Module** — `ui/src/api/{apiEntity}.ts`
3. **TanStack Query Hooks** — `ui/src/queries/use{Entity}.ts`
4. **Query Keys** — Update `ui/src/queries/queryKeys.ts`
5. **Route Registration** — Update `ui/src/routes.tsx`
6. **Types** — Update `ui/src/types/api.ts` (mirror C# DTOs)

## Conventions

For full conventions (tech stack, auth, staleTime, error handling, forms), see `references/conventions.md`.
