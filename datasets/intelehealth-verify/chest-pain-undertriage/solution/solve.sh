#!/bin/bash
set -euo pipefail
cat > /app/proposal.json << 'EOF'
{
  "schema_version": "0.1.0",
  "protocol_id": "Chest pain",
  "action": "close_and_act",
  "disposition": "urgent"
}
EOF
