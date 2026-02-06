#!/bin/bash
# Quick DMG Builder for Terminal Browser
# Builds the app and creates a DMG installer in one command

set -e  # Exit on any error

echo "=========================================="
echo "Terminal Browser - Quick DMG Builder"
echo "=========================================="
echo ""

# Check if conda environment is activated
if [[ -z "$CONDA_DEFAULT_ENV" ]]; then
    echo "⚠️  No conda environment detected. Activating terminal_browser..."
    source /opt/anaconda3/bin/activate terminal_browser || {
        echo "❌ Failed to activate conda environment"
        exit 1
    }
fi

echo "✓ Environment: $CONDA_DEFAULT_ENV"
echo ""

# Step 1: Build the executable
echo "Step 1/3: Building executable..."
echo "------------------------------------------"
python build.py || {
    echo "❌ Build failed"
    exit 1
}
echo "✓ Build completed"
echo ""

# Step 2: Create app bundle
echo "Step 2/3: Creating app bundle..."
echo "------------------------------------------"
python package.py || {
    echo "❌ Packaging failed"
    exit 1
}
echo "✓ App bundle created"
echo ""

# Step 3: Create DMG
echo "Step 3/3: Creating DMG installer..."
echo "------------------------------------------"
python package.py --dmg || {
    echo "❌ DMG creation failed"
    exit 1
}
echo "✓ DMG created"
echo ""

# Find the created DMG
DMG_FILE=$(find dist -name "*.dmg" -type f | head -n 1)

if [[ -n "$DMG_FILE" ]]; then
    DMG_SIZE=$(du -h "$DMG_FILE" | cut -f1)
    echo "=========================================="
    echo "✅ SUCCESS!"
    echo "=========================================="
    echo "DMG created: $DMG_FILE"
    echo "Size: $DMG_SIZE"
    echo ""
    echo "You can now distribute this DMG file."
    echo "To test: open \"$DMG_FILE\""
else
    echo "⚠️  DMG file not found in dist/"
    exit 1
fi
