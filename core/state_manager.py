"""State management for persistent storage"""

import json
import os
from datetime import datetime
import asyncio
import aiofiles

class StateManager:
    """Manages application state persistence with async I/O"""
    
    def __init__(self):
        self.state_file = os.path.expanduser("~/.terminal_browser_state.json")
        
    async def save_state(self, state_data):
        """Save application state to file asynchronously"""
        try:
            state_data['last_saved'] = datetime.now().isoformat()
            async with aiofiles.open(self.state_file, 'w') as f:
                await f.write(json.dumps(state_data, indent=2))
            return True
        except Exception as e:
            return False
    
    async def load_state(self):
        """Load application state from file asynchronously"""
        try:
            if os.path.exists(self.state_file):
                async with aiofiles.open(self.state_file, 'r') as f:
                    content = await f.read()
                    return json.loads(content)
            return None
        except Exception as e:
            return None
    
    async def clear_state(self):
        """Clear saved state asynchronously"""
        try:
            if os.path.exists(self.state_file):
                await asyncio.to_thread(os.remove, self.state_file)
            return True
        except Exception as e:
            return False

