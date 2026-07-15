# Testing Selection Tracking Fix

## How to Test:

1. **Start the terminal browser application**
   ```bash
   python main.py
   ```

2. **Create a terminal with identifiable lines**
   - In a terminal tab, run these commands to create numbered output:
   ```bash
   for i in {1..100}; do echo "Line $i - This is test content"; done
   ```

3. **Test the selection tracking:**
   
   **Step 1:** Select a specific line (e.g., "Line 50")
   - Click and drag to select the line, or triple-click to select the whole line
   - Note the line number in the line number column (should be around line 50)
   
   **Step 2:** Generate new output to cause scrolling
   - While keeping the selection, run another command:
   ```bash
   for i in {101..110}; do echo "New Line $i"; done
   ```
   
   **Step 3:** Verify the selection moved correctly
   - The selection should now highlight a different row number (shifted down by 10)
   - But it should STILL be highlighting "Line 50 - This is test content"
   - Copy the selection (Cmd+C on Mac) and paste somewhere to verify correct content

## Expected Behavior:

- ✅ Selection should follow the content as new lines are added
- ✅ The selected text should remain the same even though the row number changes
- ✅ Copy/paste should get the originally selected content, not wrong content

## Previous Bug:

- ❌ Selection stayed at same screen row number
- ❌ After new content, copying would get wrong line (the new line at that position)
- ❌ "Line 50" might become "Line 60" if 10 new lines were added above

## Technical Details:

The fix tracks the actual text content of the selected line and searches for it after new content is added, updating the selection coordinates to follow the content.
