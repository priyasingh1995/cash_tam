#!/bin/bash
# Push TAM Dashboard to GitHub (installs Homebrew + Git if needed, then pushes)

set -e
CDIR="/Users/priyasingh/Desktop/Interactive"
cd "$CDIR"

# 1) Use Homebrew git if available (avoids broken Xcode git)
GIT=""
for p in /opt/homebrew/bin/git /usr/local/bin/git; do
  if [ -x "$p" ]; then
    GIT="$p"
    break
  fi
done

# 2) If no Homebrew git, try to install Homebrew then git
if [ -z "$GIT" ]; then
  if ! command -v brew >/dev/null 2>&1; then
    echo "Homebrew not found. Installing Homebrew (you may be asked for your password)..."
    NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    echo "Homebrew installed."
  fi
  export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
  if ! command -v git >/dev/null 2>&1; then
    echo "Installing Git via Homebrew..."
    brew install git
  fi
  GIT="$(command -v git)"
fi

if [ -z "$GIT" ]; then
  echo "Could not find or install Git. Run: xcode-select --install"
  exit 1
fi

echo "Using Git: $GIT"

# 4) Generate static data for GitHub Pages (no backend)
if [ -f "export_dashboard_data.py" ]; then
  if [ -d ".venv" ] && [ -x ".venv/bin/python" ]; then
    .venv/bin/python export_dashboard_data.py
  elif command -v python3 >/dev/null 2>&1; then
    python3 export_dashboard_data.py
  else
    echo "Skipping export (no Python). Run export_dashboard_data.py to refresh docs/dashboard_data.json"
  fi
fi

# 5) Initialize repo and add files
if [ ! -d .git ]; then
  $GIT init
  $GIT remote add origin https://github.com/priyasingh1995/cash_tam.git
fi

$GIT add .gitignore requirements.txt tam_dashboard.py run_dashboard.sh "TAM Cash Final - Base inorganic.csv" organic_dashboard.py run_organic_dashboard.sh organic_base.xlsx export_dashboard_data.py docs/index.html docs/dashboard_data.json docs/README.md push_to_github.sh 2>/dev/null || $GIT add .
$GIT status

if [ -n "$($GIT status --porcelain)" ]; then
  $GIT commit -m "TAM + Organic dashboards; static GitHub Pages (docs/) with key numbers, no backend"
fi

$GIT branch -M main
echo "Pushing to GitHub (you may be asked for credentials)..."
$GIT push -u origin main

echo "Done. Repo: https://github.com/priyasingh1995/cash_tam"
echo "Enable GitHub Pages: Settings → Pages → Source: Deploy from branch → Branch: main, Folder: /docs"
