#!/usr/bin/env bash

# 1. Enforce sourcing
if [ "${BASH_SOURCE}" -ef "$0" ] 2>/dev/null || [ "$0" = "${BASH_SOURCE}" ]; then
    echo "❌ Error: Please source this script. Use: source common_setup.sh [project-folder]"
    exit 1
fi

# 2. Get the master company-data folder path
TARGET_FILE="${BASH_SOURCE}"
while [ -L "$TARGET_FILE" ]; do
    TARGET_DIR="$(cd -P "$(dirname "$TARGET_FILE")" && pwd)"
    TARGET_FILE="$(readlink "$TARGET_FILE")"
    [[ $TARGET_FILE != /* ]] && TARGET_FILE="$TARGET_DIR/$TARGET_FILE"
done
MASTER_DIR="$(cd -P "$(dirname "$TARGET_FILE")" && pwd)"

# 3. Determine which project folder to target
TARGET_PROJECT="$1"

if [ -z "$TARGET_PROJECT" ]; then
    echo "📂 Available projects inside company-data:"
    # List directories excluding common, crawler, or hidden folders
    select dir in $(find "$MASTER_DIR" -maxdepth 1 -type d ! -name ".*" ! -name "company-common" ! -name "company-crawler" ! -name "company-data" -exec basename {} \;); do
        if [ -n "$dir" ]; then
            TARGET_PROJECT="$dir"
            break
        fi
    done
fi

PROJECT_PATH="$MASTER_DIR/$TARGET_PROJECT"

if [ ! -d "$PROJECT_PATH" ] || [ -z "$TARGET_PROJECT" ]; then
    echo "❌ Error: Project folder '$TARGET_PROJECT' does not exist."
    return 1 2>/dev/null || exit 1
fi

echo "🚀 Setting up environment for: $TARGET_PROJECT"

# 4. Clean up corrupted previous attempts
if [ -d "$PROJECT_PATH/.venv" ]; then
    echo "🧹 Removing existing or corrupted .venv folder..."
    rm -rf "$PROJECT_PATH/.venv"
fi

# 5. Create venv using fast bypass (avoids ensurepip deadlock)
echo "⚙️ Creating virtual environment (fast bypass)..."
python3 -m venv --without-pip "$PROJECT_PATH/.venv" || python -m venv --without-pip "$PROJECT_PATH/.venv"

# 6. Activate the environment
if [ -f "$PROJECT_PATH/.venv/Scripts/activate" ]; then
    source "$PROJECT_PATH/.venv/Scripts/activate"
else
    source "$PROJECT_PATH/.venv/bin/activate"
fi

# 7. Safe fallback bootstrap for pip
echo "🔄 Bootstrapping and upgrading pip..."
python -m ensurepip --default-pip >/dev/null 2>&1 || python -m pip install --upgrade pip >/dev/null 2>&1
python -m pip install --upgrade pip

# 8. Local editable installations
COMMON_PATH="$MASTER_DIR/company-common"
CRAWLER_PATH="$MASTER_DIR/company-crawler"

if [ -d "$COMMON_PATH" ] && [ -d "$CRAWLER_PATH" ]; then
        echo "📦 Installing shared packages..."
        pip install -e "$COMMON_PATH"
        pip install "$CRAWLER_PATH"
    
    # Take user directly to their selected project
    cd "$PROJECT_PATH"
    echo "✅ Setup complete! You are now inside '$TARGET_PROJECT' with .venv active."
else
    echo "❌ Error: Shared core packages missing from company-data/ folder."
fi
