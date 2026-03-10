# Phase 85 — API-UI Contract Alignment

## Status: DONE

**Priority**: MEDIUM
**Depends on**: Phase 84 (model fixes affect DTOs)

---

## Context

Review of the bridge between C# API and React UI identified type mismatches, missing TypeScript definitions, and function signature errors that cause runtime failures or silent data loss.

---

## Items to Address

### CRITICAL

**85-1 — Notifications unreadCount Response Type Mismatch**
File (API): `api/src/FedProspector.Api/Controllers/NotificationsController.cs:41`
File (UI): `ui/src/api/notifications.ts:10`
API returns `{ unreadCount: number }`, UI expects `{ count: number }`. Runtime error when UI accesses `.count`. Update UI type to match API:
```typescript
// Before
interface UnreadCountResponse { count: number }
// After
interface UnreadCountResponse { unreadCount: number }
```

**85-2 — MarketIntel DTO Name Mismatch**
File (API): `api/src/FedProspector.Core/DTOs/Intelligence/MarketIntelDtos.cs:3`
File (UI): `ui/src/types/api.ts:1010`
API returns `MarketShareAnalysisDto`. UI defines `IntelMarketShareDto`. Different property names possible. Per MEMORY.md, `IntelMarketShareDto` was intentional to avoid collision — rename the C# DTO to match.

---

### HIGH

**85-3 — Market Share Function Returns Wrong Type**
File: `ui/src/api/awards.ts:36-37`
`getMarketShare()` declares return type `MarketShareDto[]` (simple vendor list) but the API endpoint returns `MarketShareAnalysisDto` (complex analysis object). Runtime type mismatch. Remove `getMarketShare()` (replaced by `getIntelMarketShare()`) or fix return type to match API.

**85-4 — Missing TypeScript Type for RequestLoadDto**
File (API): `api/src/FedProspector.Core/DTOs/Awards/AwardDetailResponse.cs:22`
File (UI): `ui/src/api/awards.ts:24-25`
`requestAwardLoad()` sends `{ tier }` without type safety. No TypeScript interface matches `RequestLoadDto`. Add to `ui/src/types/api.ts`:
```typescript
export interface RequestLoadDto { tier: 'usaspending' | 'fpds'; }
```

---

### MEDIUM

**85-5 — Error Handling Coverage Gap in Interceptor**
File: `ui/src/api/client.ts:48-66`
Only 429 and 409 errors dispatched to UI error handler. Other error codes (400, 403, 500) don't trigger user-facing notifications. Add catch-all error dispatch for all non-401 errors with appropriate messages per status code.

**85-6 — Auth Response Property Casing Inconsistency**
File (API): `api/src/FedProspector.Core/DTOs/AuthResult.cs`
File (UI): `ui/src/types/auth.ts:30-38`
C# PascalCase (`UserName`) auto-converts to camelCase (`userName`) in JSON. Working but creates confusion when comparing types. Add explicit `[JsonPropertyName("userName")]` attributes to C# DTOs for clarity.

---

### LOW

**85-7 — API-Only Endpoints Without UI**
File: `api/src/FedProspector.Api/Controllers/AdminController.cs:54-85`
`GET /admin/health-snapshots`, `GET /admin/api-keys`, `GET /admin/jobs` have no UI consumers. Either build admin UI tabs (Phase 76-A8 backlog) or document as API-only for future use.

**85-8 — Notification List Response Nesting**
File (API): `NotificationsController.cs:27`
File (UI): `ui/src/api/notifications.ts:6`
API returns `{ notifications: PagedResponse<T>, unreadCount: int }`. UI must destructure correctly. Verify UI handles nested response structure. Add integration test.

---

## Resolution

### Investigation Findings (reviewed before fixing)

**Fixed (4 items):**
- 85-1: Notification badge always showed 0 — UI used `.count` but API returns `.unreadCount`. Fixed in notifications.ts and TopBar.tsx.
- 85-3: Dead `getMarketShare()` function with wrong return type — removed (replaced by `getIntelMarketShare()`)
- 85-4: `requestAwardLoad()` had no type safety — added `RequestLoadDto` interface to api.ts
- 85-8: Same root cause as 85-1 — fixed together (notification unread count property name)

**Not real issues (4 items):**
- 85-2: DTO class names differ (`MarketShareAnalysisDto` vs `IntelMarketShareDto`) but property names are identical after JSON serialization. No runtime mismatch.
- 85-5: Error handling is intentionally selective — components handle 400/403/500 locally via TanStack Query. Adding global handling would cause duplicate error messages.
- 85-6: ASP.NET Core auto-converts PascalCase to camelCase. Adding `[JsonPropertyName]` attributes is pure decoration.
- 85-7: API endpoints don't require UI consumers. Not a bug.

### Files Changed
- `ui/src/api/notifications.ts` — fixed return type from `{ count }` to `{ unreadCount }`
- `ui/src/api/awards.ts` — removed dead `getMarketShare()`, added typed `RequestLoadDto` param
- `ui/src/components/layout/TopBar.tsx` — fixed `.count` to `.unreadCount`
- `ui/src/types/api.ts` — added `RequestLoadDto` interface

### Verification
- TypeScript build: `npx tsc --noEmit` passes with 0 errors
- No C# changes needed
