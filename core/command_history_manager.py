"""Command history manager with persistence and fuzzy search support"""

import json
import os
import asyncio
import aiofiles
from datetime import datetime
from typing import List, Dict, Tuple
from PyQt5.QtCore import QTimer


class CommandHistoryManager:
    """Manages command history across all terminal groups"""
    
    def __init__(self):
        self.history_file = os.path.expanduser("~/.terminal_browser_history.json")
        self.history = []  # List of dicts: {command, timestamp, group, working_dir}
        self.max_history = 10000  # Maximum number of commands to keep
        self._save_lock = asyncio.Lock()
        self._load_lock = asyncio.Lock()
        
        # Debounced save timer to batch disk writes
        self.save_timer = QTimer()
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self._do_save_sync)
        self.save_pending = False
        
        # Load synchronously on init for immediate availability
        self.load_history_sync()
    
    def add_command(self, command: str, group: str = "default", working_dir: str = ""):
        """Add a command to history"""
        if not command or not command.strip():
            return
        
        # Don't add duplicate consecutive commands
        if self.history and self.history[-1]['command'] == command:
            # Update timestamp of last command instead
            self.history[-1]['timestamp'] = datetime.now().isoformat()
            self.history[-1]['count'] = self.history[-1].get('count', 1) + 1
        else:
            entry = {
                'command': command,
                'timestamp': datetime.now().isoformat(),
                'group': group,
                'working_dir': working_dir,
                'count': 1
            }
            self.history.append(entry)
        
        # Limit history size
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]
        
        # Schedule a save (batched with 1 second delay)
        self.schedule_save()
    
    def schedule_save(self):
        """Schedule a save operation (debounced to batch multiple commands)"""
        self.save_pending = True
        # Restart timer - saves 1 second after last command
        self.save_timer.stop()
        self.save_timer.start(1000)
    
    def _do_save_sync(self):
        """Actually perform the save (sync version for timer)"""
        if self.save_pending:
            self.save_history_sync()
            self.save_pending = False
    
    async def _do_save_async(self):
        """Actually perform the save (async version)"""
        if self.save_pending:
            await self.save_history()
            self.save_pending = False
    
    def search_fuzzy(self, query: str, limit: int = 50) -> List[Dict]:
        """
        Search command history with fuzzy matching
        
        Returns list of matching commands sorted by relevance
        """
        if not query:
            # Return recent commands if no query
            return self.get_recent_commands(limit)
        
        query_lower = query.lower()
        matches = []
        
        for entry in self.history:
            command = entry['command']
            score = self._fuzzy_match_score(query_lower, command.lower())
            
            if score > 0:
                matches.append({
                    **entry,
                    'score': score
                })
        
        # Sort by score (highest first), then by timestamp (most recent first)
        matches.sort(key=lambda x: (-x['score'], -self._timestamp_to_unix(x['timestamp'])))
        
        # Remove duplicates, keeping the most recent occurrence
        seen_commands = set()
        unique_matches = []
        for match in matches:
            if match['command'] not in seen_commands:
                seen_commands.add(match['command'])
                unique_matches.append(match)
        
        return unique_matches[:limit]
    
    def _fuzzy_match_score(self, query: str, text: str) -> int:
        """
        Calculate fuzzy match score between query and text
        
        Higher score = better match
        - Exact match: 1000
        - Starts with query: 500
        - Contains query: 100
        - Fuzzy match (all chars in order): 10-99 based on gaps
        - No match: 0
        """
        if not query:
            return 0
        
        # Exact match
        if query == text:
            return 1000
        
        # Starts with query
        if text.startswith(query):
            return 500
        
        # Contains query as substring
        if query in text:
            return 100
        
        # Fuzzy match - all characters in order
        query_idx = 0
        text_idx = 0
        gaps = 0
        
        while query_idx < len(query) and text_idx < len(text):
            if query[query_idx] == text[text_idx]:
                query_idx += 1
            else:
                gaps += 1
            text_idx += 1
        
        if query_idx == len(query):
            # All query characters found in order
            # Score based on how many gaps (fewer gaps = higher score)
            return max(10, 99 - gaps)
        
        return 0
    
    def _timestamp_to_unix(self, timestamp_str: str) -> float:
        """Convert ISO timestamp string to unix timestamp"""
        try:
            dt = datetime.fromisoformat(timestamp_str)
            return dt.timestamp()
        except:
            return 0.0
    
    def get_recent_commands(self, limit: int = 50) -> List[Dict]:
        """Get most recent commands"""
        # Return unique commands in reverse order (most recent first)
        seen = set()
        recent = []
        
        for entry in reversed(self.history):
            if entry['command'] not in seen:
                seen.add(entry['command'])
                recent.append(entry)
                if len(recent) >= limit:
                    break
        
        return recent
    
    def get_commands_for_group(self, group: str, limit: int = 100) -> List[Dict]:
        """Get commands for a specific group"""
        group_commands = [e for e in self.history if e['group'] == group]
        return group_commands[-limit:]
    
    def clear_history(self):
        """Clear all command history"""
        self.history = []
        self.save_timer.stop()
        self.save_pending = False
        self.save_history_sync()
    
    async def clear_history_async(self):
        """Clear all command history asynchronously"""
        self.history = []
        self.save_timer.stop()
        self.save_pending = False
        await self.save_history()
    
    async def save_history(self):
        """Save history to file asynchronously"""
        async with self._save_lock:
            try:
                async with aiofiles.open(self.history_file, 'w') as f:
                    await f.write(json.dumps(self.history, indent=2))
            except Exception as e:
                pass
    
    def save_history_sync(self):
        """Save history to file synchronously (for backwards compatibility)"""
        try:
            with open(self.history_file, 'w') as f:
                json.dump(self.history, f, indent=2)
        except Exception as e:
            pass
    
    def flush_save(self):
        """Force immediate save (call before app exit)"""
        if self.save_pending:
            self.save_timer.stop()
            self._do_save_sync()
    
    async def flush_save_async(self):
        """Force immediate save asynchronously (call before app exit)"""
        if self.save_pending:
            self.save_timer.stop()
            await self._do_save_async()
    
    async def load_history(self):
        """Load history from file asynchronously"""
        async with self._load_lock:
            try:
                if os.path.exists(self.history_file):
                    async with aiofiles.open(self.history_file, 'r') as f:
                        content = await f.read()
                        self.history = json.loads(content)
            except Exception as e:
                self.history = []
    
    def load_history_sync(self):
        """Load history from file synchronously (for backwards compatibility)"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r') as f:
                    self.history = json.load(f)
        except Exception as e:
            self.history = []
    
    def get_stats(self) -> Dict:
        """Get statistics about command history"""
        if not self.history:
            return {
                'total_commands': 0,
                'unique_commands': 0,
                'groups': 0
            }
        
        unique_commands = set(e['command'] for e in self.history)
        unique_groups = set(e['group'] for e in self.history)
        
        return {
            'total_commands': len(self.history),
            'unique_commands': len(unique_commands),
            'groups': len(unique_groups)
        }



