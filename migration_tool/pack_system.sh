#!/bin/bash

# Configuration
BACKUP_NAME="MarketMonitor_Migration_$(date +%Y%m%d_%H%M%S).tar.gz"
EXCLUDE_LIST="--exclude=venv --exclude=__pycache__ --exclude=*.pyc --exclude=.DS_Store --exclude=.git/objects/pack --exclude=migration_tool/*.tar.gz"

echo "�� Packaging System for Migration..."
echo "   Target: $BACKUP_NAME"

# Navigate to project root
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$DIR/.."
cd "$PROJECT_ROOT"

# Check if essential data exists
if [ ! -f "user_config.json" ]; then
    echo "⚠️  user_config.json not found! Warning."
fi

if [ ! -f "user_data.db" ]; then
    echo "⚠️  user_data.db not found! Warning."
fi

# Create Tarball
# We pack the current directory content into the root of the tarball
tar -czvf "migration_tool/$BACKUP_NAME" $EXCLUDE_LIST * .secret.key .gitignore

echo "✅ Backup created successfully at: migration_tool/$BACKUP_NAME"
echo "   Size: $(du -h "migration_tool/$BACKUP_NAME" | cut -f1)"
