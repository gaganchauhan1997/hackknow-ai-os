#!/usr/bin/env bash
# ===================================================================
# Pull / verify local models: faster-whisper checkpoint + kokoro TTS.
# Both are downloaded on first use, but this script forces it ahead
# of time so the first voice request isn't slow.
# ===================================================================

set -e

YELLOW="\033[1;33m"
RESET="\033[0m"

if [ ! -d ".venv" ]; then
    echo "Run setup.sh first."
    exit 1
fi
# shellcheck disable=SC1091
source .venv/bin/activate

echo -e "${YELLOW}→ faster-whisper${RESET}"
python - <<'PY'
from faster_whisper import WhisperModel
import os
WhisperModel(os.getenv("WHISPER_MODEL", "base"), compute_type="int8")
print("  whisper cached.")
PY

echo -e "${YELLOW}→ kokoro (optional)${RESET}"
pip install kokoro >/dev/null 2>&1 || echo "  kokoro install skipped (manual install needed)."

echo "Done."
