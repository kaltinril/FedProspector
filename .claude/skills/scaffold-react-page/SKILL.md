---
name: scaffold-react-page
description: "Scaffold a new React page following FedProspect UI patterns: page component, API module, TanStack Query hooks, route registration, and MUI layout. Usage: /scaffold-react-page <PageName> <api-entity>"
argument-hint: "<PageName> <api-entity>"
disable-model-invocation: true
context: fork
agent: coder
---

**Arguments**: `$ARGUMENTS` = `<PageName> <api-entity>` (e.g., `OpportunitySearch opportunities`)

**Pre-check**: If `ui/src/` doesn't exist or Phase 20 foundation isn't in place, warn the user and stop.

**Files to Create**:

1. **Page Component** — `ui/src/pages/{PageName}/{PageName}Page.tsx`
   - Functional component with MUI layout
   - Import and use TanStack Query hooks for data
   - Use MUI components: Box, Typography, Paper, etc.
   - Include loading/error states

2. **API Module** — `ui/src/api/{apiEntity}.ts`
   - Import Axios client from `./client`
   - Export functions matching C# service methods
   - Type request/response params using types from `../types/api`
   - Pattern:
   ```typescript
   import client from './client';
   import { PagedResponse, {Entity}SearchRequest, {Entity}Dto } from '../types/api';

   export const search = (request: {Entity}SearchRequest) =>
     client.get<PagedResponse<{Entity}Dto>>('/{apiEntity}', { params: request }).then(r => r.data);

   export const getDetail = (id: string) =>
     client.get<{Entity}DetailDto>(`/{apiEntity}/${id}`).then(r => r.data);
   ```

3. **TanStack Query Hooks** — `ui/src/queries/use{Entity}.ts`
   - Import queryKeys from `./queryKeys`
   - Use `useQuery` and `useMutation` from `@tanstack/react-query`
   - Pattern:
   ```typescript
   import { useQuery } from '@tanstack/react-query';
   import { queryKeys } from './queryKeys';
   import * as api from '../api/{apiEntity}';

   export const use{Entity}Search = (request: {Entity}SearchRequest) =>
     useQuery({
       queryKey: queryKeys.{apiEntity}.search(request),
       queryFn: () => api.search(request),
       staleTime: 1000 * 60 * 5,
     });
   ```

4. **Query Keys** — Update `ui/src/queries/queryKeys.ts`
   - Add entry for the new entity:
   ```typescript
   {apiEntity}: {
     all: ['{apiEntity}'],
     search: (filters: {Entity}SearchRequest) => ['{apiEntity}', 'search', filters],
     detail: (id: string) => ['{apiEntity}', 'detail', id],
   },
   ```

5. **Route Registration** — Update `ui/src/routes.tsx`
   - Add route entry with lazy loading and auth guard

6. **Types** — Update `ui/src/types/api.ts`
   - Mirror the C# DTOs as TypeScript interfaces

**Conventions** (from Phase 20):
- Tech: Vite 6, React 19, TypeScript, MUI v6, TanStack Query v5, Axios
- API calls use relative URLs (`/api/v1/...`), Vite proxy in dev
- `withCredentials: true` on Axios (httpOnly cookie auth)
- CSRF token from non-httpOnly cookie as `X-XSRF-TOKEN` header
- staleTime: 30s notifications, 2-5min searches, 60s dashboard
- Error boundaries with react-error-boundary
- Forms: React Hook Form + Zod

For full conventions, see [references/react-conventions.md](references/react-conventions.md).
