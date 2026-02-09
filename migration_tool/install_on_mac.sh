#!/bin/bash

echo "🍎 MarketMonitor & Buyer - macOS Setup Assistant"
echo "==============================================="

# 1. Check Homebrew
if ! command -v brew &> /dev/null; then
    echo "❌ Homebrew not found. Attempting automatic installation..."
    echo "   (This will require sudo password)"
    NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    
    # Add brew to path for immediate use (standard paths)
    if [ -f "/opt/homebrew/bin/brew" ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    elif [ -f "/usr/local/bin/brew" ]; then
        eval "$(/usr/local/bin/brew shellenv)"
    fi
    
    # Verify installation
    if ! command -v brew &> /dev/null; then
        echo "🚨 Homebrew installation failed or not in PATH."
        exit 1
    fi
fi

# 2. Install Dependencies
echo "📦 Installing System Dependencies (Python3, Git)..."
brew install python3 git

# 3. Setup Virtual Environment
echo "🐍 Setting up Python Virtual Environment..."
if [ -d "venv" ]; then
    echo "   Existing venv found. Asking user..."
    read -p "   Recreate venv? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf venv
        python3 -m venv venv
    fi
else
    python3 -m venv venv
fi

# Activate
source venv/bin/activate

# 4. Install Python Libs
echo "📚 Installing Python Libraries..."
pip install --upgrade pip
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    echo "⚠️ requirements.txt not found!"
fi

# 5. Mac Specific Tweaks (Matplotlib backend etc - usually fine with default)
# Check for .secret.key
if [ ! -f ".secret.key" ]; then
    echo "⚠️ .secret.key missing! Encryption might fail."
fi

# 6. Create Launch Script
echo "🚀 Creating 'start_mac.sh'..."
cat << 'EOLAUNCH' > start_mac.sh
#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
echo "Starting MarketMonitor on macOS..."
streamlit run main.py
EOLAUNCH
chmod +x start_mac.sh

echo "==============================================="
echo "✅ Setup Complete!"
echo "   To start the app, run: ./start_mac.sh"
echo "==============================================="
