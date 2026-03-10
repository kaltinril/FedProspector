# Phase 13: Authentication, Notifications & Production Readiness

**Status**: COMPLETE (2026-03-01)
**Dependencies**: Phase 12 (Capture Management CRUD) complete
**Deliverable**: Auth endpoints, notification system, production hardening
**Repository**: `api/` (monorepo -- same repo as Python ETL)

---

## Overview

This final phase adds user authentication endpoints, an in-app notification system, and production hardening. After this phase, the API is ready for frontend integration.

---

## Tasks

### 13.1 AuthController

#### `POST /api/v1/auth/register` — Create new user account
- [x] Fields: username, email, displayName, password
- [x] Password requirements: min 8 chars, 1 uppercase, 1 lowercase, 1 number
- [x] Hash password with BCrypt (work factor 12)
- [x] Create `app_user` record + initial `app_session`
- [x] Return JWT token
- [x] Admin-only OR open registration (configurable)

#### `POST /api/v1/auth/login` — Authenticate user
- [x] Accept username + password
- [x] Verify BCrypt hash
- [x] Check account not locked (`locked_until` > NOW())
- [x] On success: reset `failed_login_attempts`, update `last_login_at`, create `app_session`, return JWT
- [x] On failure: increment `failed_login_attempts`, lock account after 5 failures for 30 minutes
- [x] Log activity: LOGIN_SUCCESS or LOGIN_FAILED

Request:
```json
{
  "username": "jdoe",
  "password": "SecurePass123"
}
```

Response:
```json
{
  "token": "eyJhbGciOi...",
  "expiresAt": "2026-03-01T14:30:00Z",
  "user": {
    "userId": 1,
    "username": "jdoe",
    "displayName": "John Doe",
    "email": "jdoe@example.com",
    "role": "user",
    "isOrgAdmin": false
  }
}
```

#### `POST /api/v1/auth/logout` — Invalidate session
- [x] Set `app_session.is_active = 'N'`
- [x] Require valid JWT (auth required)
- [x] Log activity

#### `POST /api/v1/auth/change-password` — Change password
- [x] Require current password + new password
- [x] Hash new password, update `app_user.password_hash`
- [x] Invalidate all existing sessions for user
- [x] Log activity

#### `GET /api/v1/auth/me` — Current user profile
- [x] Return current user info from JWT claims + database
- [x] Include last_login_at, role, is_org_admin

#### `PATCH /api/v1/auth/me` — Update profile
- [x] Allow update of displayName, email
- [x] Cannot change username or role (admin only)

### 13.2 NotificationsController

#### `GET /api/v1/notifications` — List user notifications
- [x] Filter: `unreadOnly` (default true), `type`
- [x] Sort by created_at DESC
- [x] Pagination standard
- [x] Includes unread count in response metadata

#### `PATCH /api/v1/notifications/{id}/read` — Mark notification as read
- [x] Set `is_read = TRUE`, `read_at = NOW()`

#### `POST /api/v1/notifications/mark-all-read` — Mark all as read
- [x] Update all unread notifications for current user

#### Notification Generation (Background/Service)
- [x] Create notifications on these events:
  - Opportunity deadline approaching (7 days, 3 days, 1 day)
  - Prospect assigned to user
  - Prospect status changed (for team members)
  - Proposal milestone due date approaching (3 days)
  - New saved search results found
  - ETL data refresh completed (admin only)
- [x] Implement as `INotificationService` called from controllers and background jobs

> **Notification polling interval**: Deferred to the frontend implementation phase. The API will provide GET/PATCH endpoints for notifications; the frontend will choose the polling frequency.

### 13.3 User Management (Admin)

#### `GET /api/v1/admin/users` — List all users
- [x] Admin only
- [x] Show: userId, username, displayName, email, role, isActive, isOrgAdmin, lastLoginAt

#### `PATCH /api/v1/admin/users/{id}` — Update user
- [x] Admin only
- [x] Change role, is_org_admin, is_active (deactivate account)
- [x] Cannot deactivate self

#### `POST /api/v1/admin/users/{id}/reset-password` — Force password reset
- [x] Admin only
- [x] Set temporary password, force change on next login
- [x] Invalidate all sessions

### 13.4 Production Hardening

#### Input Validation
- [x] FluentValidation on all request DTOs
- [x] Validate string lengths match MySQL column sizes
- [x] Sanitize HTML/script content in text fields (XSS prevention)
- [x] SQL injection prevention (parameterized queries via EF Core — already safe)

#### Rate Limiting
- [x] Use built-in `Microsoft.AspNetCore.RateLimiting` middleware (no additional NuGet package needed)
- [x] Register with `builder.Services.AddRateLimiter()` and apply with `app.UseRateLimiter()`
- [x] Configure per-endpoint rate limit policies:

| Endpoint Group | Limit | Window |
|----------------|-------|--------|
| Auth endpoints | 10 requests | per minute per IP |
| Search endpoints | 60 requests | per minute per user |
| Write endpoints | 30 requests | per minute per user |
| Admin endpoints | 30 requests | per minute per user |

#### Error Handling
- [x] Global exception handler returns consistent error DTOs
- [x] Validation errors return 400 with field-level details
- [x] Auth errors return 401/403 with clear messages
- [x] Not found returns 404 with entity type and ID
- [x] Concurrency conflicts return 409
- [x] Rate limit exceeded returns 429 with retry-after header
- [x] Unhandled exceptions return 500 with correlation ID (no stack trace in production)

#### Security Headers
- [x] Content-Security-Policy
- [x] X-Content-Type-Options: nosniff
- [x] X-Frame-Options: DENY
- [x] Strict-Transport-Security (HSTS) in production
- [x] Remove Server header

#### API Versioning
- [x] URL path versioning: `/api/v1/opportunities`, `/api/v1/prospects`
- [x] Version in response header: `X-Api-Version: 1.0`
- [x] Document versioning policy in Swagger

### 13.5 Health & Monitoring

#### `GET /health` — Health check
- [x] No auth required
- [x] Check MySQL connectivity
- [x] Check ETL data freshness per source
- [x] Return: `{ "status": "healthy|degraded|unhealthy", "checks": [...] }`

#### Structured Logging
- [x] Serilog with correlation IDs per request
- [x] Log format: JSON for production, console for development
- [x] Log levels: Information for requests, Warning for auth failures, Error for exceptions
- [x] Sensitive data redaction (passwords, tokens, PII)

#### Metrics (optional)
- [ ] Request duration per endpoint
- [ ] Error rate per endpoint
- [ ] Active sessions count
- [ ] Database query duration

### 13.6 API Documentation

- [x] Swagger UI with all endpoints documented
- [x] Request/response examples for every endpoint
- [x] Authentication flow documented (how to get token, where to send it)
- [x] Error response format documented
- [x] Rate limit documentation
- [x] Postman collection export (`api/docs/FedProspector.postman_collection.json`)

---

## Acceptance Criteria

1. [x] Registration + login + logout flow works end-to-end
2. [x] Password hashing verified with BCrypt
3. [x] Account lockout activates after 5 failed attempts
4. [x] JWT tokens expire and are rejected after expiry
5. [x] Notifications created on prospect status change
6. [x] Notifications created for approaching deadlines
7. [x] Mark-read and mark-all-read work
8. [x] Rate limiting rejects excess requests with 429
9. [x] Validation errors return 400 with field details
10. [x] All endpoints have Swagger documentation
11. [x] Health check returns MySQL status and ETL freshness
12. [x] No security headers missing (scan with SecurityHeaders.com)
13. [x] Admin can manage users (create, deactivate, reset password)
14. [x] Activity log records all auth events

---

## Post-Phase 13: Future Considerations

After all 13 phases are complete, the system will be:
- **Python ETL** (this repo): 54 tables (48 production + 6 staging) + 4 views, 39 CLI commands, 7+ API integrations, automated scheduling
- **C# API** (`api/` folder, monorepo): 44 endpoints, JWT auth, Swagger docs
- **Frontend** (TBD): Can now be built against the documented API

Future work beyond Phase 13:
- Frontend application (React, Blazor, or other)
- Tier 2 tables (compliance checklist, risk register, financial estimates, win/loss analysis)
- Tier 3 tables (clearance tracking, facility compliance, contract vehicles)
- Real-time notifications (SignalR WebSocket)
- Email notifications (SMTP integration)
- File storage (Azure Blob, AWS S3, or local)
- Multi-tenant support (multiple companies)
- Reporting/analytics dashboard (charts, exports)
