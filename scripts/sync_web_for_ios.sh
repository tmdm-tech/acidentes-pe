#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

rm -rf ios_web
mkdir -p ios_web
cp -R web/* ios_web/

# Garante um index.html para ambiente local/testes de empacotamento
cp -f web/index_simple.html ios_web/index.html

echo "ios_web sincronizado com os assets em web/."
