#!/usr/bin/env bash
set -e

if [ ! -d ".venv" ]; then
  echo "Створюю .venv і встановлюю залежності..."
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
else
  source .venv/bin/activate
fi

python3 main_gtk.py
