# Telegram Auth Backend

This document describes the backend contract for Telegram authentication. The
frontend should not use the legacy Telegram login widget. Telegram login is a
backend-owned OpenID Connect flow that ends by issuing the app's existing
access and refresh token pair.

Official Telegram docs:

- https://core.telegram.org/bots/telegram-login
- https://oauth.telegram.org/.well-known/openid-configuration

## Goal

Telegram proves the user's external identity. The Monopoly backend still owns:

- local user records
- refresh token storage and rotation
- app access JWTs
- websocket authentication
- session and game authorization

After Telegram verification, the backend must return the same auth response
shape already used by email login and registration:

```json
{
  "user": {
    "id": "user-id",
    "email": "player@example.com",
    "display_name": "Player",
    "created_at": "2026-06-12T12:00:00Z",
    "rating": 1200,
    "games_played": 0,
    "calibration_complete": false
  },
  "token": {
    "access_token": "app-access-jwt",
    "token_type": "bearer",
    "expires_in": 3600,
    "refresh_token": "opaque-refresh-token",
    "refresh_expires_in": 2592000
  }
}
```

## Telegram Setup

Create or reuse the Telegram bot that represents the app.

In BotFather, configure Web Login allowed URLs for every environment:

- local callback URL, if local tunneling is used
- staging callback URL
- production callback URL

Telegram will only redirect to URLs that are registered in BotFather. Store the
BotFather client values only on the backend.

Required backend settings:

```python
telegram_client_id: str
telegram_client_secret: str
telegram_redirect_uri: str
telegram_issuer: str = "https://oauth.telegram.org"
telegram_jwks_url: str = "https://oauth.telegram.org/.well-known/jwks.json"
frontend_telegram_callback_url: str
```

Do not expose `telegram_client_secret` to the frontend.

## API Contract

### Start Login

```text
GET /api/v1/auth/telegram/start
```

Creates a short-lived login attempt and returns the Telegram authorization URL.

Response:

```json
{
  "url": "https://oauth.telegram.org/auth?client_id=..."
}
```

The frontend redirects the browser to `url`.

### Telegram Callback

```text
GET /api/v1/auth/telegram/callback?code=<telegram-code>&state=<state>
```

This endpoint is called by Telegram after the user approves login. It does not
return app tokens directly. It verifies Telegram, creates a short-lived internal
exchange code, then redirects the browser back to the frontend:

```text
{frontend_telegram_callback_url}?code=<internal-exchange-code>
```

The internal exchange code must be single-use and short-lived.

### Exchange Internal Code

```text
POST /api/v1/auth/telegram/exchange
Content-Type: application/json

{
  "code": "internal-exchange-code"
}
```

Consumes the internal code and returns the normal `AuthResponse`.

Returning app tokens from a `POST` keeps access and refresh tokens out of
browser history, redirect logs, analytics, and referrer headers.

## OIDC Flow

### Create The Authorization URL

On `/telegram/start`:

1. Generate a random `state`.
2. Generate a random `nonce`.
3. Generate a random PKCE `code_verifier`.
4. Derive `code_challenge = base64url(sha256(code_verifier))`.
5. Store `state`, `nonce`, and `code_verifier` in Redis with a short TTL.
6. Return the Telegram authorization URL.

Authorization parameters:

```text
client_id=<telegram_client_id>
redirect_uri=<telegram_redirect_uri>
response_type=code
scope=openid profile
state=<state>
nonce=<nonce>
code_challenge=<code_challenge>
code_challenge_method=S256
```

Use the `phone` scope only if the product actually needs a verified phone
number. It requires explicit user consent.

### Exchange Telegram Code

On `/telegram/callback`:

1. Require `code` and `state`.
2. Load and delete the stored login attempt by `state`.
3. Reject missing, expired, or already consumed states.
4. Send a server-side token request to Telegram:

```text
POST https://oauth.telegram.org/token
Content-Type: application/x-www-form-urlencoded
Authorization: Basic base64(<client_id>:<client_secret>)

grant_type=authorization_code
code=<telegram-code>
redirect_uri=<telegram_redirect_uri>
client_id=<telegram_client_id>
code_verifier=<stored-code-verifier>
```

Telegram returns an `id_token`. The backend must verify that token before using
any claims.

### Verify ID Token

Validate the Telegram `id_token` with a JWT/OIDC library.

Required checks:

- verify the JWT signature against Telegram JWKS
- require `iss == "https://oauth.telegram.org"`
- require `aud == telegram_client_id`
- require `exp` to be valid
- require `nonce` to match the stored login attempt
- reject tokens without `sub`

Cache Telegram JWKS, but refresh it when a token references an unknown `kid`.

Expected useful claims:

```json
{
  "iss": "https://oauth.telegram.org",
  "aud": "123456789",
  "sub": "1234123412341234123",
  "iat": 1700000000,
  "exp": 1700003600,
  "name": "Player Name",
  "preferred_username": "player",
  "picture": "https://cdn4.telesco.pe/file..."
}
```

Telegram does not provide a separate userinfo endpoint. Treat the ID token as
the source of profile data for login.

## Persistence Model

Do not make Telegram users depend on a fake password. Prefer an identity table
or collection.

```python
class AuthProvider(StrEnum):
    PASSWORD = "password"
    TELEGRAM = "telegram"
```

Users:

```text
users
  _id
  email: optional
  display_name
  password_hash: optional
  created_at
  rating
  games_played
  calibration_complete
```

Auth identities:

```text
auth_identities
  _id
  user_id
  provider
  provider_user_id
  username
  picture_url
  created_at
  updated_at
```

Indexes:

```text
users.email unique sparse
auth_identities(provider, provider_user_id) unique
auth_identities.user_id
```

If keeping one collection is preferred, embed identities in the user document
and create an index on provider plus provider user id. Keep the same uniqueness
guarantee.

Avoid synthetic email addresses such as `telegram_<sub>@telegram.local` unless
this is explicitly accepted as a temporary migration step.

## User Linking Rules

Use handler-style provider logic instead of branching through match statements.

Required behavior:

1. Look up `AuthProvider.TELEGRAM` identity by Telegram `sub`.
2. If found, update profile fields that are safe to refresh and issue app tokens.
3. If not found, create a user and a Telegram identity atomically.
4. Use Telegram `name` for `display_name`.
5. Fall back to `preferred_username`.
6. Fall back to `Telegram User`.

Do not auto-link a Telegram identity to an existing password account by display
name or username. Telegram does not provide email by default, and username is not
a stable account-linking proof.

If account linking is needed later, require the user to be logged in with the
existing account first, then attach Telegram as a second identity.

## Service Boundaries

Keep concerns separated:

- router parses HTTP and redirects
- Telegram OIDC service builds URLs, exchanges codes, and validates ID tokens
- user service owns local user creation/linking
- token service or existing user service method issues app tokens
- repository owns Mongo access and indexes

Suggested modules for the backend:

```text
src/api/auth/router.py
src/application/services/telegram_auth_service.py
src/application/services/user_service.py
src/infra/mongo/auth_identities/repository.py
src/infra/redis/oauth_state.py
src/protocol/rest/auth.py
```

If token issuance currently lives in a private method, either extract it into a
small shared token service or add a focused public method that authenticates a
verified Telegram identity and returns `AuthResponse`.

## Error Handling

Use normal auth errors and avoid leaking Telegram internals to the client.

Recommended responses:

```text
400 invalid_request          missing code/state
401 invalid_telegram_login   bad state, failed exchange, invalid token
409 account_link_required    optional future case for explicit linking flows
503 telegram_unavailable     Telegram JWKS or token endpoint unavailable
```

Log enough backend detail to debug provider failures, but never log:

- Telegram client secret
- authorization code
- ID token
- app access token
- app refresh token
- PKCE verifier

## Frontend Contract

The frontend only needs two operations:

1. Call `GET /api/v1/auth/telegram/start` and navigate to the returned `url`.
2. On the frontend callback page, read `code` and call
   `POST /api/v1/auth/telegram/exchange`.

The exchange response is handled the same way as email login:

- store `token.access_token`
- store `token.refresh_token`
- store `user`
- redirect to `/lobby`

The frontend must not receive or store Telegram client secrets, PKCE verifiers,
or Telegram ID tokens.

## Verification Checklist

Backend tests:

1. `/telegram/start` stores `state`, `nonce`, and PKCE verifier with TTL.
2. authorization URL includes `openid`, `state`, `nonce`, and `S256` PKCE.
3. callback rejects missing or unknown `state`.
4. callback consumes `state` only once.
5. token exchange sends `code_verifier`.
6. ID token verification rejects wrong issuer.
7. ID token verification rejects wrong audience.
8. ID token verification rejects expired tokens.
9. ID token verification rejects nonce mismatch.
10. first Telegram login creates a user and identity.
11. later Telegram login reuses the same user.
12. exchange code is single-use.
13. exchange returns the existing `AuthResponse`.

Manual checks:

1. BotFather allowed URLs include the backend callback URL.
2. local/staging/prod have separate configured redirect URLs.
3. app tokens never appear in redirect URLs.
4. websocket auth still uses the app access token, not Telegram tokens.
