#!/bin/bash
set -e
echo "=========================================="
echo "  Deploying KasToko to Ubuntu Server..."
echo "=========================================="
cd /home/bablanta/Kastoko
git pull origin main
npx pm2 restart Kastoko
echo ""
echo "=========================================="
echo "  [SUCCESS] KasToko updated & restarted!"
echo "=========================================="
