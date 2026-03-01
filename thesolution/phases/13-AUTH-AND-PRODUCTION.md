# Phase 13: Authentication, Notifications & Production Readiness

**Status**: PLANNING
**Dependencies**: Phase 12 (Capture Management CRUD) complete
**Deliverable**: Auth endpoints, notification system, production hardening
**Repository**: `api/` (monorepo -- same repo as Python ETL)

---

## Overview

This final phase adds user authentication endpoints, an in-app notification system, and production hardening. After this phase, the API is ready for frontend integration.

---

## Tasks

### 13.1 AuthController

#### `POST /api/auth/register` — Create new user account
- [ ] Fields: username, email, displayName, password
- [ ] Password requirements: min 8 chars, 1 uppercase, 1 lowercase, 1 number
- [ ] Hash password with BCrypt (work factor 12)
- [ ] Create `app_user` record + initial `app_session`
- [ ] Return JWT token
- [ ] Admin-only OR open registration (configurable)

#### `POST /api/auth/login` — Authenticate user
- [ ] Accept username + password
- [ ] Verify BCrypt hash
- [ ] Check account not locked (`locked_until` > NOW())
- [ ] On success: reset `failed_login_attempts`, update `last_login_at`, create `app_session`, return JWT
- [ ] On failure: increment `failed_login_attempts`, lock account after 5 failures for 30 minutes
- [ ] Log activity: LOGIN_SUCCESS or LOGIN_FAILED

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
    "isAdmin": false
  }
}
```

#### `POST /api/auth/logout` — Invalidate session
- [ ] Set `app_session.is_active = 'N'`
- [ ] Require valid JWT (auth required)
- [ ] Log activity

#### `POST /api/auth/change-password` — Change password
- [ ] Require current password + new password
- [ ] Hash new password, update `app_user.password_hash`
- [ ] Invalidate all existing sessions for user
- [ ] Log activity

#### `GET /api/auth/me` — Current user profile
- [ ] Return current user info from JWT claims + database
- [ ] Include last_login_at, role, is_admin

#### `PATCH /api/auth/me` — Update profile
- [ ] Allow update of displayName, email
- [ ] Cannot change username or role (admin only)

### 13.2 NotificationsController

#### `GET /api/notifications` — List user notifications
- [ ] Filter: `unreadOnly` (default true), `type`
- [ ] Sort by created_at DESC
- [ ] Pagination standard
- [ ] Includes unread count in response metadata

#### `PATCH /api/notifications/{id}/read` — Mark notification as read
- [ ] Set `is_read = TRUE`, `read_at = NOW()`

#### `POST /api/notifications/mark-all-read` — Mark all as read
- [ ] Update all unread notifications for current user

#### Notification Generation (Background/Service)
- [ ] Create notifications on these events:
  - Opportunity deadline approaching (7 days, 3 days, 1 day)
  - Prospect assigned to user
  - Prospect status changed (for team members)
  - Proposal milestone due date approaching (3 days)
  - New saved search results found
  - ETL data refresh completed (admin only)
- [ ] Implement as `INotificationService` called from controllers and background jobs

> **Notification polling interval**: Deferred to the frontend implementation phase. The API will provide GET/PATCH endpoints for notifications; the frontend will choose the polling frequency.

### 13.3 User Management (Admin)

#### `GET /api/admin/users` — List all users
- [ ] Admin only
- [ ] Show: userId, username, displayName, email, role, isActive, isAdmin, lastLoginAt

#### `PATCH /api/admin/users/{id}` — Update user
- [ ] Admin only
- [ ] Change role, is_admin, is_active (deactivate account)
- [ ] Cannot deactivate self

#### `POST /api/admin/users/{id}/reset-password` — Force password reset
- [ ] Admin only
- [ ] Set temporary password, force change on next login
- [ ] Invalidate all sessions

### 13.4 Production Hardening

#### Input Validation
- [ ] FluentValidation on all request DTOs
- [ ] Validate string lengths match MySQL column sizes
- [ ] Sanitize HTML/script content in text fields (XSS prevention)
- [ ] SQL injection prevention (parameterized queries via EF Core — already safe)

#### Rate Limiting
- [ ] Use built-in `Microsoft.AspNetCore.RateLimiting` middleware (no additional NuGet package needed)
- [ ] Register with `builder.Services.AddRateLimiter()` and apply with `app.UseRateLimiter()`
- [ ] Configure per-endpoint rate limit policies:

| Endpoint Group | Limit | Window |
|----------------|-------|--------|
| Auth endpoints | 10 requests | per minute per IP |
| Search endpoints | 60 requests | per minute per user |
| Write endpoints | 30 requests | per minute per user |
| Admin endpoints | 30 requests | per minute per user |

#### Error Handling
- [ ] Global exception handler returns consistent error DTOs
- [ ] Validation errors return 400 with field-level details
- [ ] Auth errors return 401/403 with clear messages
- [ ] Not found returns 404 with entity type and ID
- [ ] Concurrency conflicts return 409
- [ ] Rate limit exceeded returns 429 with retry-after header
- [ ] Unhandled exceptions return 500 with correlation ID (no stack trace in production)

#### Security Headers
- [ ] Content-Security-Policy
- [ ] X-Content-Type-Options: nosniff
- [ ] X-Frame-Options: DENY
- [ ] Strict-Transport-Security (HSTS) in production
- [ ] Remove Server header

#### API Versioning
- [ ] URL path versioning: `/api/v1/opportunities`, `/api/v1/prospects`
- [ ] Version in response header: `X-Api-Version: 1.0`
- [ ] Document versioning policy in Swagger

### 13.5 Health & Monitoring

#### `GET /health` — Health check
- [ ] No auth required
- [ ] Check MySQL connectivity
- [ ] Check ETL data freshness per source
- [ ] Return: `{ "status": "healthy|degraded|unhealthy", "checks": [...] }`

#### Structured Logging
- [ ] Serilog with correlation IDs per request
- [ ] Log format: JSON for production, console for development
- [ ] Log levels: Information for requests, Warning for auth failures, Error for exceptions
- [ ] Sensitive data redaction (passwords, tokens, PII)

#### Metrics (optional)
- [ ] Request duration per endpoint
- [ ] Error rate per endpoint
- [ ] Active sessions count
- [ ] Database query duration

### 13.6 API Documentation

- [ ] Swagger UI with all endpoints documented
- [ ] Request/response examples for every endpoint
- [ ] Authentication flow documented (how to get token, where to send it)
- [ ] Error response format documented
- [ ] Rate limit documentation
- [ ] Postman collection export

---

## Acceptance Criteria

1. [ ] Registration + login + logout flow works end-to-end
2. [ ] Password hashing verified with BCrypt
3. [ ] Account lockout activates after 5 failed attempts
4. [ ] JWT tokens expire and are rejected after expiry
5. [ ] Notifications created on prospect status change
6. [ ] Notifications created for approaching deadlines
7. [ ] Mark-read and mark-all-read work
8. [ ] Rate limiting rejects excess requests with 429
9. [ ] Validation errors return 400 with field details
10. [ ] All endpoints have Swagger documentation
11. [ ] Health check returns MySQL status and ETL freshness
12. [ ] No security headers missing (scan with SecurityHeaders.com)
13. [ ] Admin can manage users (create, deactivate, reset password)
14. [ ] Activity log records all auth events

---

## Post-Phase 13: Future Considerations

After all 13 phases are complete, the system will be:
- **Python ETL** (this repo): 54 tables (48 production + 6 staging) + 4 views, 38 CLI commands, 7+ API integrations, automated scheduling
- **C# API** (`api/` folder, monorepo): 21+ endpoints, JWT auth, Swagger docs
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
