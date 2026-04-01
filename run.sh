#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ -f .env ]; then
  export "$(grep -v '^#' .env | grep -v '^\s*$' | xargs)"
elif [ -f .env.local ]; then
  export "$(grep -v '^#' .env.local | grep -v '^\s*$' | xargs)"
else
  echo "No .env or .env.local found. Copy .env.template to .env and add your key."
  exit 1
fi

if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  echo "ANTHROPIC_API_KEY is not set. Check your .env file."
  exit 1
fi

python3 scripts/generate.py
