# Backend deployment (VPS)

Production backend stack for a single VPS. The frontend runs on **Vercel**; this
host runs the API behind **Caddy** (automatic HTTPS), with **MongoDB** and
**Redis** on a private network.

```
Vercel (FE) ──fetch /api/v1/* + wss /ws/*──▶ caddy :443 (https://API_DOMAIN)
                                                └─▶ api (uvicorn :8000)
             mongodb, redis: internal only
```

Files in this directory:

| File | Role |
|------|------|
| `docker-compose.yml` | `caddy` + `api` + `mongodb` + `redis` (build context = `..`) |
| `Caddyfile`          | TLS + proxy `API_DOMAIN` → `api:8000` |
| `.env.example`       | secrets/config template |

> Run all commands **from this directory** (`MonopolyBE/deploy`) so `.env` is
> picked up and the relative paths (`..` build context, `./Caddyfile`) resolve.

---

## First deploy (fresh Ubuntu 22.04/24.04)

### 1. DNS
Add a record at your registrar and confirm it resolves before deploying:

| Type | Name | Value |
|------|------|-------|
| A    | `api` (→ `api.yourdomain.com`) | VPS public IPv4 |
| AAAA | `api` | VPS public IPv6 *(if any)* |

```bash
dig +short api.yourdomain.com    # → your VPS IP
```

### 2. Install Docker
```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER && newgrp docker
docker compose version
```

### 3. Firewall (only SSH + web)
```bash
sudo ufw allow OpenSSH
sudo ufw allow 80,443/tcp
sudo ufw enable
```
Port 80 is required for the Let's Encrypt HTTP challenge. Do **not** expose
27017/6379 — they stay on the internal network.

### 4. Configure + launch
```bash
git clone <your-repo-url> monopoly
cd monopoly/MonopolyBE/deploy
cp .env.example .env
# edit .env: API_DOMAIN, ACME_EMAIL, FRONTEND_ORIGIN (your Vercel URL),
#            and strong secrets — openssl rand -hex 32

docker compose up -d --build
docker compose ps                 # all "healthy"
docker compose logs -f caddy      # wait for "certificate obtained successfully"
```

### 5. Verify
```bash
curl https://api.yourdomain.com/health   # → {"status":"ok"}
curl https://api.yourdomain.com/ready    # → mongo + redis "ok"
```

### 6. Connect to Vercel
- **Vercel** → Settings → Environment Variables: `NEXT_PUBLIC_API_URL =
  https://api.yourdomain.com` (baked at build time → redeploy after setting).
- **Here**: `FRONTEND_ORIGIN` in `.env` must exactly match your Vercel origin
  (scheme + host, no trailing slash). After changing it:
  `docker compose up -d api`.

---

## Day-2 operations

```bash
# logs
docker compose logs -f api

# update after a git push
git pull && docker compose up -d --build

# Mongo backup (schedule via cron)
docker compose exec -T mongodb \
  mongodump --username "$MONGO_ROOT_USERNAME" --password "$MONGO_ROOT_PASSWORD" \
  --authenticationDatabase admin --archive --gzip > backup-$(date +%F).gz
```

## Notes

- **Keep the `caddy_data` volume** — it stores the TLS certs. Deleting it forces
  re-issuance and can hit Let's Encrypt rate limits. Mongo data lives in
  `mongo_data`.
- The API runs as a **single uvicorn process** by design: the Redis backplane
  fans out broadcasts, but the connection manager and disconnect-grace state are
  process-local. Running multiple replicas needs a cross-node presence mechanism
  first (see `../docs/game-protocol.md`). One process handles this workload fine.
- **Vercel preview deployments** have dynamic `*-git-*.vercel.app` URLs that
  won't match an exact `FRONTEND_ORIGIN`, so they'll be CORS-blocked against this
  API. Use the production domain, or ask to add `allow_origin_regex` support.
