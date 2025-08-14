#!/usr/bin/env bash
set -euo pipefail
TAG="pre-phaseB-$(date +%Y%m%d-%H%M%S)"
echo "[*] Creating safety commit & tag: $TAG"
git add -A || true
git commit -m "Safety snapshot $TAG" || true
git tag -a "$TAG" -m "Safety snapshot before Phase B"
echo "[*] Creating archive: ../$TAG.tar.gz"
git archive --format=tar.gz -o "../$TAG.tar.gz" HEAD
echo "[✓] Backup done: tag=$TAG, archive=../$TAG.tar.gz"
