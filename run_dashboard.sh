#!/bin/bash
# TAM Dashboard - one-command setup and run
# Run in Terminal: cd /Users/priyasingh/Desktop/Interactive && bash run_dashboard.sh

set -e
cd "$(dirname "$0")"

echo "=== TAM Dashboard launcher ==="

# Use existing venv if already set up
if [ -d ".venv" ] && [ -x ".venv/bin/streamlit" ]; then
  echo "Using existing .venv..."
  . .venv/bin/activate
  exec streamlit run tam_dashboard.py
fi

# Try uv
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
if command -v uv >/dev/null 2>&1; then
  echo "Using uv..."
  uv venv .venv
  . .venv/bin/activate
  uv pip install -r requirements.txt
  exec streamlit run tam_dashboard.py
fi

# Try Homebrew Python
for py in /opt/homebrew/bin/python3 /usr/local/bin/python3; do
  if [ -x "$py" ]; then
    echo "Using $py..."
    "$py" -m venv .venv
    . .venv/bin/activate
    pip install -r requirements.txt
    exec streamlit run tam_dashboard.py
  fi
done

# Try system python3 with venv
if command -v python3 >/dev/null 2>&1; then
  echo "Trying system python3 + venv..."
  if python3 -m venv .venv 2>/dev/null; then
    . .venv/bin/activate
    pip install -r requirements.txt
    exec streamlit run tam_dashboard.py
  fi
fi

# Install uv and retry
echo "Installing uv (no sudo needed)..."
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
if command -v uv >/dev/null 2>&1; then
  echo "Using uv..."
  uv venv .venv
  . .venv/bin/activate
  uv pip install -r requirements.txt
  exec streamlit run tam_dashboard.py
fi

echo ""
echo "Could not run the dashboard automatically."
echo "Do one of the following, then run this script again:"
echo "  1. Install Homebrew (https://brew.sh), then: brew install python"
echo "  2. Install Python from https://www.python.org/downloads/"
echo "  3. Open a new terminal and run: bash run_dashboard.sh"
exit 1
