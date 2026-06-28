#!/bin/bash
echo "✦ Setting up Asterism..."

# Check Python version
python3 --version || { echo "Python 3.10+ required"; exit 1; }

# Create venv
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt -q

# Install asterism in editable mode
pip install -e . -q

# Create .env if not exists
if [ ! -f .env ]; then
  cp .env.example .env
  echo "✦ Created .env — add your ANTHROPIC_API_KEY"
fi

# Init database
asterism init

echo ""
echo "✦ Asterism ready."
echo ""
echo "Next steps:"
echo "  1. Add your API key to .env"
echo "  2. Export your Claude data from claude.ai/settings"
echo "  3. Run: asterism crawl --source claude --path YOUR_EXPORT_PATH"
echo "  4. Run: asterism view"
echo ""
