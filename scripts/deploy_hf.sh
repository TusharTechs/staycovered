#!/usr/bin/env bash
# Deploy StayCovered to a Hugging Face Docker Space (free CPU basic hardware).
#   scripts/deploy_hf.sh <hf-username>/<space-name>
# Prereqs (one-time, done by you): create the Space (SDK: Docker, hardware: CPU basic - free), add Space secrets
# NEBIUS_API_KEY and TAVILY_API_KEY (and optionally SC_ADMIN_TOKEN), and run `hf auth login` in your terminal.
# Pushes the committed HEAD (not uncommitted changes), without research/, raw source files, or local runtime data.
set -euo pipefail
SPACE="${1:?usage: deploy_hf.sh <hf-username>/<space-name>}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

echo "==> staging committed HEAD"
git -C "$ROOT" archive HEAD | tar -x -C "$STAGE"
rm -rf "$STAGE/research" "$STAGE/sources/raw" "$STAGE/.claude" "$STAGE/data/runtime" "$STAGE/bench/results/judge_key.csv"

# Space card (Hugging Face reads the YAML header); the GitHub README is kept as README_PROJECT.md
mv "$STAGE/README.md" "$STAGE/README_PROJECT.md"
cat > "$STAGE/README.md" <<CARD
---
title: StayCovered
emoji: 🛡️
colorFrom: green
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
license: apache-2.0
short_description: Medicaid work-requirement copilot grounded in rules as of a date
---

$(cat "$STAGE/README_PROJECT.md")
CARD
# Dockerfile copies README.md; keep that working
echo "==> pushing to https://huggingface.co/spaces/$SPACE"
cd "$STAGE"
git init -q -b main
git -c user.name="Tushar Agarwal" -c user.email="tusharaggarwal274@gmail.com" add -A
git -c user.name="Tushar Agarwal" -c user.email="tusharaggarwal274@gmail.com" commit -q -m "Deploy StayCovered"
git push -f "https://huggingface.co/spaces/$SPACE" main
echo "==> pushed. Build logs: https://huggingface.co/spaces/$SPACE?logs=build"
echo "==> app: https://$(echo "$SPACE" | tr '/' '-' | tr '[:upper:]' '[:lower:]').hf.space"
