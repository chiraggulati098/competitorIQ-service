echo "🔧 Installing Python dependencies..."
pip install -r requirements.txt || { echo "❌ Failed to install Python packages"; exit 1; }

echo "📦 Installing Playwright system dependencies..."
playwright install-deps || { echo "❌ Failed to install Playwright dependencies"; exit 1; }

echo "🎭 Installing Playwright browsers..."
playwright install || { echo "❌ Failed to install Playwright browsers"; exit 1; }

echo "✅ Setup complete!"