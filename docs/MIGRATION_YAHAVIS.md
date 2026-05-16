# YAHAVIS → HackKnow AI OS Migration

Reuse your existing `github.com/gaganchauhan1997/YahavisAI` repo as a thin client around the HackKnow AI OS core.

## 1. Add HackKnow as a submodule

```bash
cd YahavisAI
git submodule add https://github.com/<you>/hackknow-ai-os.git core
```

## 2. Point YAHAVIS at the core

In your existing entrypoint (`yahavis/main.py` or wherever), replace any bespoke LLM / planner code with:

```python
import sys, asyncio
sys.path.insert(0, "core")          # the submodule
from core.orchestrator import HackKnowOS

async def main():
    os_ = HackKnowOS()
    await os_.boot()
    while True:
        line = input(f"{os_.agents['ceo'].cfg.get('role','')}> ")
        result = await os_.execute(line)
        print(result.summary)

asyncio.run(main())
```

## 3. Migrate the rotating API pool

Your existing pool (Groq/Gemini/Cohere/Mistral/Together/OpenRouter/HuggingFace) is already supported. Add each key once via the UI at `/` → API Key Vault, or via the API:

```bash
curl -X POST http://localhost:8787/keys \
  -H "content-type: application/json" \
  -d '{"provider":"groq","secret":"gsk_...","label":"groq-1"}'
```

Up to 50 per provider, 12 providers supported.

## 4. Keep your branding

`config/settings.py` honours `HACKKNOW_ASSISTANT_NAME`. Set:

```
HACKKNOW_ASSISTANT_NAME=Yahavi
HACKKNOW_ASSISTANT_MODE=jarvis
```

…and `core/i18n.style_prefix` will keep calling you "Boss".

## 5. Reuse YAHAVIS PWA / Electron shell

Replace the WebView URL in your existing PWA / Electron config with `http://localhost:8787` (or your deployed HackKnow URL). The UI at `ui/app.html` is mobile-friendly and includes a service worker, so the Web Speech mic flow still works on Android.

## 6. Drop YAHAVIS-specific skills into `skills/`

If you have YAHAVIS-specific tooling (WhatsApp client, custom WooCommerce flows, etc.), expose them as HackKnow skills:

```python
# skills/whatsapp/__init__.py
manifest = {"description": "...", "parameters": {...}}
async def run(**kwargs): ...
```

They auto-register at boot.

## 7. CI

Add `.github/workflows/ci.yml` (copied from HackKnow). Smoke tests run in <30s; Docker image is published to Docker Hub on every push to main.

Done. YAHAVIS is now a brand on top of HackKnow AI OS.
