#!/usr/bin/env bash
# One-command launcher for the Shibuya hotel monitor.
#
# Usage, from the japan-hotels folder:
#   ./run.sh
#
# It will:
#   1. Create .venv if missing
#   2. Install/upgrade dependencies
#   3. Verify .env exists with required keys
#   4. Launch the bot in the foreground
#
# Leave the terminal window open while the bot runs.

set -e
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo ">> Creating virtualenv…"
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo ">> Installing dependencies…"
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

if [ ! -f .env ]; then
  echo ""
  echo "!! .env not found. Creating it from the template."
  echo "   Open .env in a text editor and paste your TELEGRAM_BOT_TOKEN"
  echo "   (and SERPAPI_KEY if you have one), then run ./run.sh again."
  cp .env.example .env
  exit 1
fi

if ! grep -q '^TELEGRAM_BOT_TOKEN=[^[:space:]]\{20,\}' .env; then
  echo ""
  echo "!! TELEGRAM_BOT_TOKEN in .env looks empty or short."
  echo "   Open .env, paste your token after TELEGRAM_BOT_TOKEN=, and re-run."
  exit 1
fi

echo ">> Launching bot. Press Ctrl-C to stop."
echo ""
exec python -m app.main
