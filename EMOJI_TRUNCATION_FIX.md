# Emoji Truncation Fix

## Problem

Terminal output was being truncated after emojis, specifically the warning emoji `⚠️`. 

**Example:**
- **Expected:** `industry_management_backend  | 2025-11-12 08:29:49 | WARNING | ⚠️ Display name not found`
- **Actual:** `industry_management_backend  | 2025-11-12 08:29:49 | WARNING | ⚠`

## Root Cause

The issue was caused by a bug in the **pyte** terminal emulator library (version 0.8.2) when handling wide characters, specifically:

1. The emoji `⚠️` consists of two Unicode characters:
   - U+26A0 (WARNING SIGN) 
   - U+FE0F (VARIATION SELECTOR-16)

2. According to `wcwidth`, this emoji takes **2 columns** in a terminal display

3. When pyte processes this wide character, it miscalculates the cursor position and **truncates all subsequent text** on that line

4. This is a known issue with pyte v0.8.2 (the latest version) and there are no newer versions available

## Solution

Added a `sanitize_wide_chars()` method that pre-processes all terminal output **before** feeding it to pyte. This method:

1. Replaces problematic emoji characters with ASCII equivalents:
   - `⚠️` → `[!]` (warning)
   - `❌` → `[X]` (error)
   - `✅` → `[✓]` (success)
   - Plus 20+ other common emojis

2. Removes the VARIATION SELECTOR-16 character (U+FE0F) which often causes issues when combined with other characters

3. Preserves all text content while working around pyte's wide character bugs

## Implementation

**File:** `ui/pyte_terminal_widget.py`

### Added Method (line ~1812)
```python
@staticmethod
def sanitize_wide_chars(text):
    """Sanitize text to work around pyte wide character handling issues."""
    emoji_replacements = {
        '⚠️': '[!]',  # WARNING SIGN + VARIATION SELECTOR-16
        '⚠': '[!]',   # WARNING SIGN alone
        # ... 20+ more emoji mappings
    }
    for emoji, replacement in emoji_replacements.items():
        text = text.replace(emoji, replacement)
    text = text.replace('\uFE0F', '')
    return text
```

### Modified Method (line ~2737)
```python
def handle_output(self, data):
    """Handle output from PTY - buffer for async processing"""
    try:
        text = data.decode('utf-8', errors='replace')
        
        # Sanitize wide characters to prevent pyte truncation bugs
        text = self.sanitize_wide_chars(text)  # ← ADDED THIS LINE
        
        # ... rest of method unchanged
```

## Testing

Verified the fix works correctly:

```python
# Input
test_line = "industry_management_backend  | 2025-11-12 08:29:49 | WARNING | ⚠️ Display name not found"

# After sanitization and pyte processing
output = "industry_management_backend  | 2025-11-12 08:29:49 | WARNING | [!] Display name not found"

# ✓ Full text preserved
# ✓ Emoji replaced with readable ASCII equivalent [!]
# ✓ No truncation
```

## Impact

- **All terminal output** with problematic emojis will now display correctly
- Emojis are replaced with **readable ASCII equivalents** in square brackets
- **No data loss** - all text after emojis is preserved
- Works with Docker logs, application output, and any terminal program
- **Backward compatible** - no breaking changes

## Alternative Considered

We could upgrade or patch pyte, but:
- Version 0.8.2 is the latest (no newer versions available)
- Patching pyte's wide character handling is complex and risky
- The ASCII replacement approach is simple, reliable, and user-friendly

## Future Improvements

If a newer version of pyte is released with proper wide character support, we can:
1. Add a preference setting to enable/disable emoji sanitization
2. Allow users to use native emojis if pyte is fixed
3. Keep the ASCII replacements as a fallback option
