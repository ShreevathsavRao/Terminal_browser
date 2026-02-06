#!/bin/bash

# Test script for selection tracking
# Run this in the terminal browser to test the selection fix

echo "=========================================="
echo "Selection Tracking Test"
echo "=========================================="
echo ""

# Create numbered lines for testing
echo "Creating test lines..."
for i in {1..20}; do
    echo "Line $i - Original content"
done

echo ""
echo "=========================================="
echo "NOW: Select one of the lines above"
echo "     (e.g., Line 10)"
echo "=========================================="
echo ""
echo "Press Enter when ready to add new lines..."
read

# Add new lines that should cause the selection to shift
echo ""
echo "Adding 5 new lines..."
for i in {21..25}; do
    echo "NEW Line $i - Just added"
    sleep 0.2
done

echo ""
echo "=========================================="
echo "CHECK: Your selection should have moved"
echo "       to stay on the same content!"
echo "=========================================="
echo ""
echo "If you selected 'Line 10', it should still"
echo "be highlighted even though it's now at a"
echo "different row position on screen."
echo ""
echo "Try copying (Cmd+C) and pasting to verify"
echo "you get the correct content."
