#!/usr/bin/env bash
set -e

if [ ! -d ".venv" ]; then
  echo "Не знайдено .venv. Спочатку запустіть: ./setup.sh"
  exit 1
fi

source .venv/bin/activate
python3 main.py
