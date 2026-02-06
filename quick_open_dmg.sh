#!/bin/bash
# Quick script to build DMG and open it immediately

set -e

echo "🚀 Building and opening Terminal Browser DMG..."

# Run the quick DMG builder
./quick_dmg.sh

# Find and open the DMG
DMG_FILE=$(find dist -name "*.dmg" -type f | head -n 1)

if [[ -n "$DMG_FILE" ]]; then
    echo ""
    echo "📂 Opening DMG..."
    open "$DMG_FILE"
    echo "✅ Done! DMG is now open."
else
    echo "❌ DMG file not found"
    exit 1
fi
