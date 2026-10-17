#!/usr/bin/env bash
set -euo pipefail

# Regenerate profile SVGs and push if anything changed.
# Tokens are never stored — sourced from gh's local credential store at runtime.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "→ fetching token from gh..."
export GH_TOKEN
GH_TOKEN="$(gh auth token 2>/dev/null)" || {
  echo "ERROR: could not get a token from 'gh auth token'."
  echo "Run 'gh auth login' first."
  exit 1
}

echo "→ generating SVGs..."
python3 generate.py

echo "→ checking for changes..."
if git diff --quiet -- light.svg dark.svg snake-light.svg snake-dark.svg; then
  echo "No SVG changes — nothing to commit."
  exit 0
fi

echo "→ committing..."
git add light.svg dark.svg snake-light.svg snake-dark.svg
git commit -m "chore: refresh profile card and snake"

echo "→ pushing..."
git push origin main

echo "Done."
