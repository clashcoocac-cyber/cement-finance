#!/bin/bash
# Bot setup script

echo "🔧 Cement Finance Bot Setup"
echo "============================"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "Creating .env file from .env.example..."
    cp .env.example .env
    echo "✅ .env file created"
    echo ""
    echo "⚠️  IMPORTANT: Edit .env and add your BOT_TOKEN"
    echo "   Get it from @BotFather on Telegram"
    echo ""
fi

# Create temp directory
mkdir -p temp_pdfs
echo "✅ temp_pdfs directory created"

# Install requirements
echo ""
echo "Installing requirements..."
pip install -r requirements.txt

echo ""
echo "🎉 Setup complete!"
echo ""
echo "To start the bot, run:"
echo "  python run_bot.py"
echo ""
echo "Make sure you have set BOT_TOKEN in .env file"
