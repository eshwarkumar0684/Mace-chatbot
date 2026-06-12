#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$(pwd)"

exec uvicorn backend.app:app --host 0.0.0.0 --port "${PORT:-8000}"
