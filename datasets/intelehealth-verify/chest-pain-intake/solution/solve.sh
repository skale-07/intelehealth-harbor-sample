#!/bin/bash
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
cp "$DIR/agent.py" /app/agent.py
