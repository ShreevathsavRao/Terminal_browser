"""Notes manager with persistence for tab-specific notes"""

import json
import os
import asyncio
import aiofiles
from datetime import datetime
from typing import List, Dict
from PyQt5.QtCore import QTimer
import uuid


class NotesManager:
    """Manages notes for terminal tabs"""
    
    def __init__(self):
        self.notes_file = os.path.expanduser("~/.terminal_browser_notes.json")
        self.notes = {}  # Dict: {tab_id: [note_objects]}
        self._save_lock = asyncio.Lock()
        self._load_lock = asyncio.Lock()
        
        # Debounced save timer to batch disk writes
        self.save_timer = QTimer()
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self._do_save_sync)
        self.save_pending = False
        
        # Load synchronously on init for immediate availability
        self.load_notes_sync()
    
    def get_notes_for_tab(self, tab_id: str) -> List[Dict]:
        """Get all notes for a specific tab"""
        if tab_id not in self.notes:
            self.notes[tab_id] = []
        return self.notes[tab_id]
    
    def add_note(self, tab_id: str, title: str = "Untitled Note", content: str = "") -> Dict:
        """Add a new note to a tab"""
        if tab_id not in self.notes:
            self.notes[tab_id] = []
        
        note = {
            'id': str(uuid.uuid4()),
            'title': title,
            'content': content,
            'created': datetime.now().isoformat(),
            'modified': datetime.now().isoformat()
        }
        
        self.notes[tab_id].append(note)
        self.schedule_save()
        return note
    
    def update_note(self, tab_id: str, note_id: str, title: str = None, content: str = None):
        """Update an existing note"""
        if tab_id not in self.notes:
            return
        
        for note in self.notes[tab_id]:
            if note['id'] == note_id:
                if title is not None:
                    note['title'] = title
                if content is not None:
                    note['content'] = content
                note['modified'] = datetime.now().isoformat()
                self.schedule_save()
                break
    
    def delete_note(self, tab_id: str, note_id: str):
        """Delete a note from a tab"""
        if tab_id not in self.notes:
            return
        
        self.notes[tab_id] = [note for note in self.notes[tab_id] if note['id'] != note_id]
        self.schedule_save()
    
    def get_note(self, tab_id: str, note_id: str) -> Dict:
        """Get a specific note"""
        if tab_id not in self.notes:
            return None
        
        for note in self.notes[tab_id]:
            if note['id'] == note_id:
                return note
        return None
    
    def schedule_save(self):
        """Schedule a debounced save"""
        self.save_pending = True
        self.save_timer.start(1000)  # Save after 1 second of inactivity
    
    def _do_save_sync(self):
        """Synchronous save operation"""
        if not self.save_pending:
            return
        
        try:
            with open(self.notes_file, 'w') as f:
                json.dump(self.notes, f, indent=2)
            self.save_pending = False
        except Exception as e:
            pass
    
    def load_notes_sync(self):
        """Load notes from file synchronously"""
        if not os.path.exists(self.notes_file):
            self.notes = {}
            return
        
        try:
            with open(self.notes_file, 'r') as f:
                self.notes = json.load(f)
        except Exception as e:
            self.notes = {}
    
    async def load_notes_async(self):
        """Load notes from file asynchronously"""
        async with self._load_lock:
            if not os.path.exists(self.notes_file):
                self.notes = {}
                return
            
            try:
                async with aiofiles.open(self.notes_file, 'r') as f:
                    content = await f.read()
                    self.notes = json.loads(content)
            except Exception as e:
                self.notes = {}
    
    async def save_notes_async(self):
        """Save notes to file asynchronously"""
        async with self._save_lock:
            try:
                async with aiofiles.open(self.notes_file, 'w') as f:
                    await f.write(json.dumps(self.notes, indent=2))
                self.save_pending = False
            except Exception as e:
                pass
    
    def force_save(self):
        """Force immediate save"""
        self._do_save_sync()
