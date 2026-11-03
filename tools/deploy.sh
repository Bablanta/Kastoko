#!/bin/bash
set -e
echo "=========================================="
echo "  Deploying KasToko to Ubuntu Server..."
echo "=========================================="
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"
git fetch origin main
git reset --hard origin/main
npx pm2 restart Kastoko
echo ""
echo "=========================================="
echo "  [SUCCESS] KasToko updated & restarted!"
echo "=========================================="
