# Component Templates

Code templates for scaffolding a new React page. Replace `{PageName}`, `{Entity}`, and `{apiEntity}` with actual names (e.g., `OpportunitySearch`, `Opportunity`, `opportunities`).

## 1. Page Component — `ui/src/pages/{PageName}/{PageName}Page.tsx`

- Functional component with MUI layout
- Import and use TanStack Query hooks for data
- Use MUI components: Box, Typography, Paper, etc.
- Include loading/error states

## 2. API Module — `ui/src/api/{apiEntity}.ts`

```typescript
import client from './client';
import { PagedResponse, {Entity}SearchRequest, {Entity}Dto } from '../types/api';

export const search = (request: {Entity}SearchRequest) =>
  client.get<PagedResponse<{Entity}Dto>>('/{apiEntity}', { params: request }).then(r => r.data);

export const getDetail = (id: string) =>
  client.get<{Entity}DetailDto>(`/{apiEntity}/${id}`).then(r => r.data);
```

## 3. TanStack Query Hooks — `ui/src/queries/use{Entity}.ts`

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

## 4. Query Keys — Update `ui/src/queries/queryKeys.ts`

Add entry for the new entity:

```typescript
{apiEntity}: {
  all: ['{apiEntity}'],
  search: (filters: {Entity}SearchRequest) => ['{apiEntity}', 'search', filters],
  detail: (id: string) => ['{apiEntity}', 'detail', id],
},
```

## 5. Route Registration — Update `ui/src/routes.tsx`

Add route entry with lazy loading and auth guard.

## 6. Types — Update `ui/src/types/api.ts`

Mirror the C# DTOs as TypeScript interfaces.
