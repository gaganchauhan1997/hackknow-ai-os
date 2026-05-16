#!/usr/bin/env bash
# =====================================================
# HackKnow AI OS — one-shot installer
# =====================================================
set -e

GREEN="\033[0;32m"
YELLOW="\033[1;33m"
RESET="\033[0m"

banner() {
    echo -e "${GREEN}"
    echo "  ╔════════════════════════════════════════════════╗"
    echo "  ║         HackKnow AI OS — Installer             ║"
    echo "  ║   Free intelligence. Infinite capability.      ║"
    echo "  ╚════════════════════════════════════════════════╝"
    echo -e "${RESET}"
}

banner

# --- 1. Python virtualenv ---
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}[1/5] Creating Python virtualenv...${RESET}"
    python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

# --- 2. Python deps ---
echo -e "${YELLOW}[2/5] Installing Python dependencies...${RESET}"
pip install --upgrade pip wheel setuptools >/dev/null
pip install -r requirements.txt

# --- 3. Playwright browsers ---
echo -e "${YELLOW}[3/5] Installing Playwright browsers...${RESET}"
python -m playwright install chromium

# --- 4. Local models (optional) ---
echo -e "${YELLOW}[4/5] Pulling local models (whisper + kokoro)...${RESET}"
bash scripts/pull_local_models.sh || echo "  ↳ Skipped local models (optional)."

# --- 5. .env scaffold ---
echo -e "${YELLOW}[5/5] Bootstrapping .env...${RESET}"
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "  ↳ Created .env from template. Edit it to add free-tier API keys."
fi

echo -e "${GREEN}"
echo "  ✓ HackKnow AI OS is ready."
echo "    Next:"
echo "      1) Edit .env with your free-tier API keys"
echo "      2) bash scripts/start_server.sh"
echo "      3) Or run a demo:  python demos/voice_demo.py"
echo -e "${RESET}"
