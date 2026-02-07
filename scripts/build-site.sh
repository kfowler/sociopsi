#!/usr/bin/env bash
set -euo pipefail

PROJ_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Copy PDFs into site-src so MkDocs can serve them
mkdir -p "$PROJ_ROOT/site-src/research/papers"
cp "$PROJ_ROOT/docs/research/"*.pdf "$PROJ_ROOT/site-src/research/papers/" 2>/dev/null || {
    echo "Warning: No PDFs found in docs/research/. Build the LaTeX sources first."
    echo "  cd docs/research && xelatex -interaction=nonstopmode <file>.tex"
}

if [ "${1:-}" = "serve" ]; then
    uv run mkdocs serve
else
    uv run mkdocs build
fi
