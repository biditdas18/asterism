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

echo ""
echo "✦ Setup complete. Next steps:"
echo ""
echo "  1. Run: asterism init"
echo "     (guided setup — asks for your name and API key)"
echo ""
echo "  2. Export your Claude data:"
echo "     claude.ai → Settings → Export Data"
echo "     Check email → download zip → unzip"
echo ""
echo "  3. Run: asterism crawl --source claude --path path/to/conversations.json"
echo ""
echo "  4. Your constellation opens automatically."
echo ""
