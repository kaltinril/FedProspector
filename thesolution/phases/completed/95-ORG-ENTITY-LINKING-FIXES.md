# Phase 95: Organization — Entity Linking Tab Fixes

## Status: COMPLETE

## Problem
The Organization page's Entity Linking tab (Phase 91 deliverable) has a critical search bug and several quality gaps compared to the other Organization tabs (Settings, Members, Invites).

Searching SAM.gov entities returns **400 Bad Request** on virtually every search. The tab also lacks error handling, uses hardcoded query keys, and swallows errors silently.

## Root Cause
`OrgEntitiesTab.tsx` sends the raw search string as BOTH `name` AND `uei` parameters. The backend `EntitySearchRequestValidator` requires `uei` to be exactly 12 characters when provided, so any non-12-character search term fails validation.

## Tasks

### Task 1: Fix entity search — stop sending search term as UEI unconditionally

**File:** `ui/src/pages/organization/OrgEntitiesTab.tsx` (lines 99-103)

**Current (broken):**
```typescript
const result = await searchEntities({
  name: searchQuery,
  uei: searchQuery,     // ← always sent, fails validation when ≠ 12 chars
  pageSize: 10,
});
```

**Fix:** Only set `uei` if the input looks like a UEI (exactly 12 alphanumeric characters):
```typescript
const trimmed = searchQuery.trim();
const isUei = /^[A-Z0-9]{12}$/i.test(trimmed);
const result = await searchEntities({
  name: isUei ? undefined : trimmed,
  uei: isUei ? trimmed : undefined,
  pageSize: 10,
});
```

### Task 2: Show search error feedback to user

**File:** `ui/src/pages/organization/OrgEntitiesTab.tsx` (lines 105-106)

The `catch` block in `handleSearch` sets `searchResults = []` but shows nothing to the user. Add an error state and render an `<Alert severity="error">` when the search API call fails, so the user understands why no results appeared.

### Task 3: Add error handling for linked entities query

**File:** `ui/src/pages/organization/OrgEntitiesTab.tsx` (line 58)

The `useQuery` for `getLinkedEntities` destructures only `data` and `isLoading` — no `isError` handling. If the GET fails, the user sees the misleading "No entities linked yet" message. Add `isError` + `<ErrorState>` component, consistent with the other Organization tabs.

### Task 4: Use centralized query keys instead of hardcoded strings

**Files:** `ui/src/pages/organization/OrgEntitiesTab.tsx` (lines 58-93), `ui/src/queries/queryKeys.ts`

The tab uses inline query key strings (`['org-entities']`, `['org-profile']`, `['org-naics']`, `['org-certifications']`) for the query and all mutation invalidations. The rest of the Organization page uses centralized `queryKeys.organization.*`. If centralized keys ever change, this tab's cache invalidation silently breaks.

**Fix:** Import `queryKeys` and use the centralized key definitions. Ideally, move queries/mutations into `useOrganization.ts` hooks to match the pattern of other tabs.

### Task 5: Add error handling for deactivate and refresh mutations

**File:** `ui/src/pages/organization/OrgEntitiesTab.tsx` (lines 76-93)

`deactivateMutation` and `refreshMutation` have no `onError` handlers. The template only checks `linkMutation.isError` (line 150). If unlinking or refreshing an entity fails, the user gets no feedback.

**Fix:** Add `onError` callbacks with snackbar notifications (consistent with Members/Invites tabs which use `useSnackbar()` from notistack).

### Task 6: CAGE code search not implemented despite placeholder text

**File:** `ui/src/pages/organization/OrgEntitiesTab.tsx`

The search input placeholder says "Search by name, UEI, or CAGE code" but `EntitySearchParams` in `ui/src/api/entities.ts` has no `cage` field and the backend `EntitySearchRequest` doesn't support it either. Either add CAGE code support or update the placeholder to match reality.

## Files to Modify

| File | Change |
|------|--------|
| `ui/src/pages/organization/OrgEntitiesTab.tsx` | Fix search params, add error handling, use centralized query keys, add mutation error feedback |
| `ui/src/api/entities.ts` | Verify/update `EntitySearchParams` type |
| `ui/src/queries/queryKeys.ts` | Add `organization.entities` key if missing |
| `ui/src/hooks/useOrganization.ts` | Move entity queries/mutations here (optional but recommended) |

## Related (Not in Scope)
- **401 on `/auth/me`**: Covered by Phase 94 (auth interceptor excludes all `/auth/` URLs from token refresh). See Phase 94 Task 3 and issues H4/M8.
- **Activity Log tab**: Placeholder only — separate phase when ready to implement.

## Verification
1. Search for a company name (e.g., "msone") → results returned, no 400 error
2. Search for a 12-char UEI → searches by UEI correctly
3. Search with network error → user sees error alert
4. Link/unlink entity with backend failure → user sees snackbar error
5. Linked entities query failure → ErrorState shown, not "No entities linked yet"
6. Build succeeds, existing tests pass
