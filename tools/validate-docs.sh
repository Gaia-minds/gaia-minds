#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root_dir"

if command -v markdownlint-cli2 >/dev/null 2>&1; then
  echo "Running markdownlint-cli2..."
  markdownlint-cli2 "**/*.md"
else
  echo "markdownlint-cli2 not found; install it to run markdown checks."
fi

if command -v lychee >/dev/null 2>&1; then
  echo "Running lychee..."
  lychee --config .lychee.toml "**/*.md"
else
  echo "lychee not found; install it to run link checks."
fi

