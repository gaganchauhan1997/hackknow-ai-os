# 🚀 Deploy HackKnow AI OS — pick one (each takes ≤ 5 minutes)

This repo ships with **three** one-click deploy paths. Pick whichever you prefer; you only need ONE.

---

## Option A — Render (recommended, free)

1. Open <https://dashboard.render.com/select-repo?type=blueprint>
2. Select `gaganchauhan1997/hackknow-ai-os` → "Connect"
3. Render reads `render.yaml` automatically. Click **Apply**.
4. Paste your free-tier API keys in the env-var screen (or skip — zero-key Ollama works locally only).
5. Wait ~4 min for the image to build. You get a `https://hackknow-ai-os.onrender.com` URL.

Done. The free plan sleeps after 15 min idle but wakes on first request.

---

## Option B — Fly.io (closest to India, generous free tier)

```bash
brew install flyctl                  # or: curl -L https://fly.io/install.sh | sh
flyctl auth signup                   # one-time
flyctl deploy --remote-only          # uses fly.toml in repo root
```

Region is `bom` (Mumbai) for fastest latency from India.

---

## Option C — HuggingFace Spaces (free, Docker, 16GB RAM)

1. Get an HF token: <https://huggingface.co/settings/tokens> (write scope).
2. Add it to this repo: GitHub → Settings → Secrets → Actions → New repository secret → `HF_TOKEN`.
3. Push any commit (or click **Actions → HackKnow Deploy → Run workflow** in the GitHub UI).
4. Your space appears at `https://huggingface.co/spaces/gaganchauhan1997/hackknow-ai-os`.

---

## Option D — Self-hosted (your VPS)

```bash
ssh boss@your-server
git clone https://github.com/gaganchauhan1997/hackknow-ai-os.git
cd hackknow-ai-os
docker compose up -d                 # api + ollama + qdrant + redis + flowise
```

Then point `hackknow.com` (Cloudflare DNS) at the server IP → done.

---

## UI on Cloudflare Pages (optional, ultra-fast CDN)

If you want the UI served from Cloudflare's edge:

1. Get a Cloudflare API token at <https://dash.cloudflare.com/profile/api-tokens> with **Account → Cloudflare Pages → Edit**.
2. Add `CF_API_TOKEN` and `CF_ACCOUNT_ID` as GitHub repo secrets.
3. Push or click **Actions → HackKnow Deploy → Run workflow**.

The UI lands at `https://hackknow.pages.dev`, with WebSocket calls falling back to your backend host.

---

## hackknow.com DNS (Cloudflare)

Once you pick a backend host:

| Record | Name | Target | Proxy |
|--------|------|--------|-------|
| CNAME  | app  | `hackknow-ai-os.onrender.com` (or your fly/HF URL) | ✓ |
| CNAME  | @    | `hackknow.pages.dev` (if using Pages for UI)        | ✓ |

Then `https://app.hackknow.com` is your live AI OS.

---

## What you'll need (one of each)

- **Backend host** — Render / Fly / HF Spaces / VPS (pick one)
- **At least 1 free LLM key** — Groq is fastest, free, 30 RPM. Get at <https://console.groq.com>
- **Domain DNS** — Cloudflare for hackknow.com (already in your account)

That's the whole shopping list.
