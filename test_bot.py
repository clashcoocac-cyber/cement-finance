"""
Testing script for bot components
Run this to verify everything is working correctly
"""
import sys
from pathlib import Path

# Add project to path
project_path = Path(__file__).parent
sys.path.insert(0, str(project_path))

# Test imports
print("Testing imports...")
try:
    from bot.config.settings import get_settings, load_env
    print("✅ Settings imported successfully")
except Exception as e:
    print(f"❌ Settings import failed: {e}")
    sys.exit(1)

try:
    from bot.services.database import CustomerService
    print("✅ Database service imported successfully")
except Exception as e:
    print(f"❌ Database service import failed: {e}")

try:
    from bot.services.pdf_generator import PDFGenerator
    print("✅ PDF generator imported successfully")
except Exception as e:
    print(f"❌ PDF generator import failed: {e}")

try:
    from bot.handlers import start_router, phone_router
    print("✅ Handlers imported successfully")
except Exception as e:
    print(f"❌ Handlers import failed: {e}")

print("\n✅ All imports successful! Bot is ready.")
print("\nNext steps:")
print("1. Create .env file with BOT_TOKEN")
print("2. Run: python run_bot.py")
