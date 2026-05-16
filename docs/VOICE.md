# HackKnow Voice — Cloned, Bilingual, Not Robotic

## Voices

The repo ships with Boss's reference samples under `voice_samples/`:

- `laksh_male_soft.mp3` — male, soft & emotional
- `priyanka_female_soft.mp3` — female, soft & romantic

## Engines

| Engine     | Quality      | Speed     | Languages | Notes                                  |
|------------|--------------|-----------|-----------|----------------------------------------|
| **XTTS-v2** (default) | studio-grade | ~real-time | en, hi + 15 more | best clone fidelity from 6s sample |
| F5-TTS    | excellent    | very fast | en, zh    | optional fast fallback                 |
| OpenVoice V2 | natural   | fast      | multi     | optional fallback                      |
| Kokoro    | clear        | very fast | en, hi    | low-latency fallback for short replies |

## Installing XTTS-v2

```bash
pip install coqui-tts
# weights auto-download on first call (~1.8 GB)
```

The skill is at `skills/voice_clone/__init__.py`. It auto-routes to XTTS when installed, F5 if not, OpenVoice as a final option.

## Live mic loop

`ws://localhost:8787/voice` — send raw WAV bytes, get:
1. `{ user_text, lang }` (faster-whisper STT)
2. `{ assistant_text }` (orchestrator reply)
3. binary WAV of the cloned voice (XTTS-v2)

## Wake word

The Voice Studio in the UI uses the browser's Web Speech API as a wake-word + STT fallback. For true on-device wake-word, install [picovoice porcupine](https://picovoice.ai/products/porcupine/) and call it from `skills/voice/`.

## Tips for "not robotic"

- Always pass `lang="hi"` for Devanagari text. XTTS picks up Hindi prosody.
- Keep replies under ~400 chars per chunk for the smoothest delivery.
- For male voice match Boss's Laksh sample; for female use Priyanka.
- Avoid markdown / emoji in TTS text — they read literally.
