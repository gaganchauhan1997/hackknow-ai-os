# Multi-Key Vault Guide

> Paste 50 keys. Big task in. Micro-tasks fan out. Keys rotate. Refresh resumes work. Zero-key mode falls back to Ollama.

## How it works

```
   user goal
       │
       ▼
┌───────────────────┐
│   Task Shredder   │  ← LLM call that emits a JSON DAG of atomic micro-tasks
└────────┬──────────┘
         ▼
┌────────────────────┐
│   Durable Queue    │  ← .cache/queue.json — survives restarts
└────────┬───────────┘
         ▼
┌────────────────────┐    pick fresh key
│    LLM Router      │ ──────────────────▶ ┌────────────────┐
└────────┬───────────┘                     │   Key Vault    │
         ▼                                  │  (up to 50/p)  │
   429 / quota?  ◀───── record_usage ─────  └────────────────┘
         │
   mark key cooling → try next
         │
   all exhausted? ── pause job, schedule wake_after(refresh_seconds)
         │
   key refreshed → resume cursor
```

## Adding keys

### UI

Open `http://localhost:8787` → **API Key Vault** → pick provider → paste secret → Add.

### API

```bash
curl -X POST http://localhost:8787/keys \
  -H "content-type: application/json" \
  -d '{"provider":"groq","secret":"gsk_xxx","label":"groq-1","tier":"free"}'
```

### Supported providers

`groq`, `gemini`, `openai`, `anthropic`, `cohere`, `mistral`, `together`, `openrouter`, `deepseek`, `perplexity`, `huggingface`. **Up to 50 keys per provider.**

## Capacity meter

`GET /meter` returns:

```json
{
  "active_keys": 18,
  "cooling_keys": 2,
  "total_keys": 20,
  "tokens_remaining_today": 8_400_000,
  "tokens_daily_capacity": 12_000_000,
  "percent_remaining": 70,
  "estimated_hours_at_normal_load": 50.4,
  "capabilities": {
    "simple_chat_turns": {"possible": 4200, "cost_per_unit": 2000, "description": "Short Hindi/English chat reply"},
    "marketing_campaigns": {"possible": 186, "cost_per_unit": 45000, "description": "End-to-end 7-day campaign plan"},
    "reel_scripts": {"possible": 1050, "cost_per_unit": 8000, "description": "15-second reel script + shotlist"},
    ...
  },
  "zero_key_mode": false
}
```

The UI shows this as a circular meter + a grid of "what you can do today" — counted in units (campaigns, articles, audits, reels, code features, etc.).

## Free-tier defaults

| Provider     | Refresh | RPM | Daily tokens (free)    |
|--------------|---------|-----|------------------------|
| Groq         | 60s     | 30  | 500K                   |
| Gemini       | 60s     | 15  | 1M (Flash)             |
| Cohere       | 1h      | 20  | 200K                   |
| Mistral      | 60s     | 60  | 500K                   |
| Together     | 60s     | 60  | 300K                   |
| OpenRouter   | 60s     | 20  | 200K                   |
| HuggingFace  | 60s     | 30  | 100K                   |
| Ollama       | —       | ∞   | local                  |

**Paid keys** (any provider) get a 10× daily budget multiplier in the meter — set `tier: "paid"` when adding.

## Zero-key mode

When zero keys are present *or* every provider is exhausted, the router falls through to **Ollama** at `OLLAMA_BASE_URL`. First call auto-pulls the configured model (`OLLAMA_MODEL`, default `llama3.1:8b`).

```bash
# install Ollama (once)
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.1:8b      # or qwen2.5:3b for faster responses
```

## Resume-on-refresh

The queue persists at `.cache/queue.json`. If you Ctrl-C the server mid-job, the next boot picks up exactly where it left off — same cursor, same micro-task list.

## Tips for getting epic capability from 50 keys

- Spread across providers. Groq + Gemini + OpenRouter together give you ~3M tokens/day on the free tier with 6 keys.
- Set non-critical agents (`automation`, `excel_dashboard`, `content_creator`) to `llm_tier: fast` so they consume less budget per call.
- Use the **Task Shredder** for any goal longer than ~280 chars — it pre-splits the work so a single rate-limit doesn't stall a whole campaign.
- Drop your most valuable paid key (Anthropic / OpenAI) at the front. The vault auto-prefers keys with more remaining budget.
