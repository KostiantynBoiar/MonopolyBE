# Frontend Auth Guide

This document covers every auth flow the backend exposes. All endpoints are
under `GET /api/v1` or `POST /api/v1`.

---

## Token model

After any successful login or registration the backend returns an `AuthResponse`:

```json
{
  "user": {
    "id": "uuid",
    "email": "player@example.com",   // null for Telegram-only accounts
    "display_name": "Player",
    "created_at": "2026-06-12T12:00:00Z",
    "rating": 800,
    "games_played": 0,
    "calibration_complete": false
  },
  "token": {
    "access_token": "eyJ...",
    "token_type": "bearer",
    "expires_in": 3600,
    "refresh_token": "opaque-string",
    "refresh_expires_in": 2592000
  }
}
```

**Store both tokens.** `access_token` lives for `expires_in` seconds (1 hour).
`refresh_token` lives for `refresh_expires_in` seconds (30 days). Store them in
`localStorage` or a secure cookie — never in a URL or log.

Send the access token as a header on every authenticated request:

```
Authorization: Bearer <access_token>
```

---

## Refresh tokens

When an access token expires (the API returns `401`), exchange the refresh
token for a fresh pair:

```
POST /auth/refresh
Content-Type: application/json

{ "refresh_token": "<stored_refresh_token>" }
```

The response is a full `AuthResponse`. Overwrite both stored tokens.
Refresh tokens are **single-use** — a token consumed once cannot be reused.
If the refresh token is also expired, the user must log in again.

---

## Email / password flows

### Register

```
POST /auth/register
Content-Type: application/json

{
  "email": "player@example.com",
  "password": "min8chars",
  "display_name": "Player"
}
```

Returns `AuthResponse` (201). Store tokens and redirect to lobby.

Errors:

| Status | detail | Meaning |
|--------|--------|---------|
| 409 | Email already registered | Email is taken |
| 422 | validation error | Password < 8 chars or display_name < 2 chars |

### Login

```
POST /auth/login
Content-Type: application/json

{ "email": "player@example.com", "password": "..." }
```

Returns `AuthResponse` (200).

Errors:

| Status | detail | Meaning |
|--------|--------|---------|
| 401 | Invalid email or password | Wrong credentials |

### Logout

```
POST /auth/logout
Content-Type: application/json

{ "refresh_token": "<stored_refresh_token>" }
```

Returns 204. Revokes the refresh token server-side. Clear both tokens from storage.

---

## Telegram login

This is a three-step browser-redirect flow. The frontend never touches Telegram
directly. All secrets stay on the backend.

### Step 1 — Get the Telegram URL

```
GET /auth/telegram/start
```

No auth required. Response:

```json
{ "url": "https://oauth.telegram.org/auth?client_id=...&state=...&..." }
```

**Redirect the browser** (or open a popup) to `url`. The user authenticates
with Telegram.

### Step 2 — The callback page

Telegram redirects the browser back to your frontend callback page, e.g.
`/auth/telegram/callback`, with a `code` query parameter:

```
https://yourapp.com/auth/telegram/callback?code=<exchange-code>
```

This page has one job: read `code` from the URL and call step 3. The code
is single-use and expires in 5 minutes.

> **Why the extra hop?**  
> Telegram sends its `code` to the _backend_ first
> (`TELEGRAM_REDIRECT_URI`). The backend verifies it with Telegram, creates
> or finds the local user, then produces a short-lived internal code and
> redirects to your frontend. This keeps Telegram tokens, PKCE verifiers,
> and secrets entirely off the frontend.

### Step 3 — Exchange for app tokens

```
POST /auth/telegram/exchange
Content-Type: application/json

{ "code": "<code from URL>" }
```

Returns `AuthResponse`. Store tokens and redirect to lobby.

Errors:

| Status | detail | Meaning |
|--------|--------|---------|
| 401 | Invalid or expired exchange code | Code already used or expired |

### Full flow diagram

```
Frontend                Backend                Telegram
   |                       |                       |
   |-- GET /telegram/start -->                      |
   |<-- { url } -----------|                        |
   |                       |                        |
   |------- redirect browser to url -------------->|
   |                                                |-- user approves
   |<------ redirect to TELEGRAM_REDIRECT_URI ------|
   |              (backend callback URL)            |
   |                       |                        |
   |              backend verifies with Telegram    |
   |              backend creates/finds user        |
   |              backend mints exchange code       |
   |                       |                        |
   |<--- redirect to /auth/telegram/callback?code= -|
   |                       |                        |
   |-- POST /telegram/exchange { code } ----------->|
   |<-- AuthResponse -------|                        |
```

---

## Linking Telegram to an existing email account

A user who registered with email/password can attach Telegram as an alternative
login method from their settings page. This reuses the same Telegram redirect
flow, but it requires an active session.

### Step 1 — Get the Telegram URL (authenticated)

```
GET /auth/telegram/connect/start
Authorization: Bearer <access_token>
```

Response is the same shape as `/telegram/start`:

```json
{ "url": "https://oauth.telegram.org/auth?..." }
```

Redirect the browser to `url`.

### Step 2 — The connect callback page

Telegram redirects through the backend, which links the identity and then
redirects the browser to your **connect callback page**, e.g.
`/settings/telegram` (configured as `FRONTEND_TELEGRAM_CONNECT_URL`).

The backend appends one query parameter:

| Query string | Meaning |
|---|---|
| `?telegram_linked=true` | Telegram was successfully linked |
| `?error=telegram_account_already_linked` | This Telegram account is already linked to a different Monopoly account |
| `?error=account_already_has_telegram` | Your account already has a Telegram identity linked |
| `?error=telegram_error` | Telegram verification failed (try again) |

Read the query string and show the appropriate message. No POST call is needed
for this flow — the backend handles everything server-side before redirecting.

### Step 3 (optional) — Refresh current user

If linking succeeded, call `/auth/me` to get the updated user object if you
display account status in the UI.

```
GET /auth/me
Authorization: Bearer <access_token>
```

---

## Adding an email and password to a Telegram account

A user who signed in with Telegram and has no email can add one from their
settings page.

```
POST /auth/link/email
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "email": "player@example.com",
  "password": "min8chars"
}
```

Returns `MeResponse` with the updated user (200).

Once complete, the user can log in with either email/password **or** Telegram.

Errors:

| Status | detail | Meaning |
|--------|--------|---------|
| 409 | Account already has an email address | Account already has an email — nothing to do |
| 409 | Email already registered | Email is taken by a different account |
| 422 | validation error | Password < 8 chars |

---

## Current user

```
GET /auth/me
Authorization: Bearer <access_token>
```

Returns:

```json
{
  "user": {
    "id": "uuid",
    "email": "player@example.com",   // null for Telegram-only accounts
    "display_name": "Player",
    "created_at": "...",
    "rating": 800,
    "games_played": 0,
    "calibration_complete": false
  }
}
```

---

## Detecting account capabilities from the user object

The `user.email` field tells you what the account can do:

| `user.email` | Has email login | Can link Telegram |
|---|---|---|
| `"player@example.com"` | Yes | Yes (use `/telegram/connect/start`) |
| `null` | No | Already signed in via Telegram |

Use this to decide which options to show in the settings UI:

- **Email present** → show "Connect Telegram" button (unless Telegram is already
  linked, which you can track client-side from whether the user arrived via
  Telegram login).
- **Email null** → show "Add email and password" form (`POST /auth/link/email`).

> The backend does not yet expose a `GET /auth/identities` endpoint to list
> all linked providers. If you need to know whether Telegram is already linked
> to a password account, store this information client-side after a successful
> connect, or request it to be added as a backend endpoint.

---

## Error handling reference

All errors follow this shape:

```json
{ "detail": "Human-readable message" }
```

Common status codes:

| Code | When |
|------|------|
| 400 | Malformed request |
| 401 | Missing/expired token, wrong credentials, bad Telegram state |
| 409 | Conflict (duplicate email, already linked) |
| 422 | Request body failed validation (Pydantic) |
| 503 | Telegram service unreachable |

---

## Environment variables the backend needs

These are set by whoever deploys the backend. The frontend only needs to know
its own callback page paths, which must match the configured backend values.

| Variable | What the frontend needs to match |
|---|---|
| `FRONTEND_TELEGRAM_CALLBACK_URL` | Page that calls `POST /telegram/exchange` |
| `FRONTEND_TELEGRAM_CONNECT_URL` | Page that reads `?telegram_linked` or `?error` |
