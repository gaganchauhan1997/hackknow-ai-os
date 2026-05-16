# HackKnow AI OS — Deployment Playbook

## TL;DR

```bash
git clone <your-fork>/hackknow-ai-os && cd hackknow-ai-os
cp .env.example .env && nano .env       # paste any free-tier keys
docker compose up -d                    # api + ollama + qdrant + redis + flowise
open http://localhost:8787
```

That's it. The full stack is running, with a local Ollama fallback for zero-key mode.

---

## 1. Local (Python venv)

```bash
bash setup.sh              # creates .venv, installs deps, prepares Playwright + voice
nano .env
bash scripts/start_server.sh
```

## 2. Docker (single host)

```bash
docker build -t hackknow-ai-os:latest .
docker run -p 8787:8787 --env-file .env hackknow-ai-os:latest
```

## 3. Docker Compose (recommended for production single-node)

`docker compose up -d` spins up:

| Service  | Port  | Purpose                          |
|----------|-------|----------------------------------|
| api      | 8787  | HackKnow FastAPI server          |
| ollama   | 11434 | Local LLM for zero-key fallback  |
| qdrant   | 6333  | Optional vector store            |
| redis    | 6379  | Background-task broker (future)  |
| flowise  | 3000  | Visual workflow editor           |

## 4. Railway / Render / Fly.io

Push to GitHub, connect the repo, and set these env vars:

```
GROQ_API_KEY=…
GEMINI_API_KEY=…
OPENROUTER_API_KEY=…
OLLAMA_BASE_URL=https://your-ollama   # optional
PORT=8787
```

Railway auto-detects `Dockerfile`. Render uses the same. Fly.io: `fly launch` → `fly deploy`.

## 5. Vercel + Render (split: front + back)

- Deploy the `ui/` folder as a static site on Vercel.
- Deploy the FastAPI server on Render or Fly.io.
- Set `NEXT_PUBLIC_API_BASE` in Vercel to the Render URL, then update the few `fetch("/...")` calls in `ui/app.html` to prefix with that base.

## 6. Kubernetes / Helm

Skeleton chart at `deploy/helm/` (generate with `helm create hackknow`). Mount `.env` as a Secret, expose `api` via Ingress, and back the cache with a PVC.

## 7. Desktop (Tauri)

```bash
cd packaging/tauri
cargo tauri build
# → installers under src-tauri/target/release/bundle/
```

The Tauri shell connects to a running HackKnow API at `http://localhost:8787`. Bundle the API as a sidecar binary if you want a single-click install.

## 8. Android (Capacitor or PWA)

- **PWA (no code)**: open the deployed site in Chrome on Android → "Add to Home screen".
- **Capacitor (native APK)**:
  ```bash
  cd packaging/capacitor
  npx cap init "HackKnow" com.hackknow.aios --web-dir=../../ui
  npx cap add android
  cd android && ./gradlew assembleDebug
  ```

## 9. Securing the API

In production, put the FastAPI server behind nginx / Cloudflare with HTTPS:

```nginx
server {
    server_name hackknow.com;
    listen 443 ssl;
    ssl_certificate     /etc/letsencrypt/live/hackknow.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/hackknow.com/privkey.pem;
    location / {
        proxy_pass         http://127.0.0.1:8787;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade $http_upgrade;
        proxy_set_header   Connection "upgrade";
        proxy_set_header   Host $host;
    }
}
```

Then enable basic auth, JWT, or API-key middleware in `server/api.py`.

## 10. CI/CD

`.github/workflows/ci.yml` runs the smoke tests on every push and pushes Docker images to Docker Hub on main. Add secrets:
- `DOCKERHUB_USER`
- `DOCKERHUB_TOKEN`

Done.
