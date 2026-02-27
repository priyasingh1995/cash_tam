#!/bin/bash
# Organic Incidence Dashboard - one-command setup and run
# Run in Terminal: cd /Users/priyasingh/Desktop/Interactive && bash run_organic_dashboard.sh

set -e
cd "$(dirname "$0")"

echo "=== Organic Incidence Dashboard launcher ==="

if [ -d ".venv" ] && [ -x ".venv/bin/streamlit" ]; then
  echo "Using existing .venv..."
  . .venv/bin/activate
  exec streamlit run organic_dashboard.py
fi

export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
if command -v uv >/dev/null 2>&1; then
  echo "Using uv..."
  uv venv .venv 2>/dev/null || true
  . .venv/bin/activate
  uv pip install -r requirements.txt
  exec streamlit run organic_dashboard.py
fi

for py in /opt/homebrew/bin/python3 /usr/local/bin/python3; do
  if [ -x "$py" ]; then
    echo "Using $py..."
    "$py" -m venv .venv 2>/dev/null || true
    . .venv/bin/activate
    pip install -r requirements.txt
    exec streamlit run organic_dashboard.py
  fi
done

if command -v python3 >/dev/null 2>&1; then
  if python3 -m venv .venv 2>/dev/null; then
    . .venv/bin/activate
    pip install -r requirements.txt
    exec streamlit run organic_dashboard.py
  fi
fi

echo "Could not run. Install Python, then run: streamlit run organic_dashboard.py"
exit 1
