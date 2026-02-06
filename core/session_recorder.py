"""Session Recorder for recording and playing back command sequences"""

import json
import os
from datetime import datetime
from PyQt5.QtCore import QSettings

class SessionRecorder:
    """Manages recording and playback of command sessions"""
    
    def __init__(self):
        self.settings = QSettings()
        self.recordings = {}  # {recording_id: recording_data}
        self.load_recordings()
    
    def get_recordings_file(self):
        """Get the path to the recordings file"""
        settings_dir = os.path.dirname(self.settings.fileName())
        return os.path.join(settings_dir, "session_recordings.json")
    
    def load_recordings(self):
        """Load recordings from file"""
        recordings_file = self.get_recordings_file()
        if os.path.exists(recordings_file):
            try:
                with open(recordings_file, 'r') as f:
                    self.recordings = json.load(f)
                # Migrate old format (list of strings) to new format (list of dicts)
                for recording_id, recording in self.recordings.items():
                    if 'commands' in recording and recording['commands']:
                        if isinstance(recording['commands'][0], str):
                            # Old format: convert to new format with directory info
                            recording['commands'] = [
                                {'command': cmd, 'directory': None}
                                for cmd in recording['commands']
                            ]
            except Exception as e:
                self.recordings = {}
        else:
            self.recordings = {}
    
    def save_recordings(self):
        """Save recordings to file"""
        recordings_file = self.get_recordings_file()
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(recordings_file), exist_ok=True)
            
            with open(recordings_file, 'w') as f:
                json.dump(self.recordings, f, indent=2)
        except Exception as e:
            pass
    
    def create_recording(self, name, commands, description="", start_directory=None):
        """Create a new recording
        
        Args:
            name: Recording name
            commands: List of command dicts with 'command' and optional 'directory' keys,
                     or list of strings (for backward compatibility)
            description: Optional description
            start_directory: Starting directory where recording began
        """
        recording_id = f"recording_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Normalize commands to dict format
        normalized_commands = []
        for cmd in commands:
            if isinstance(cmd, str):
                normalized_commands.append({'command': cmd, 'directory': None})
            elif isinstance(cmd, dict):
                normalized_commands.append({
                    'command': cmd.get('command', ''),
                    'directory': cmd.get('directory')
                })
            else:
                normalized_commands.append({'command': str(cmd), 'directory': None})
        
        recording = {
            'id': recording_id,
            'name': name,
            'description': description,
            'commands': normalized_commands,
            'start_directory': start_directory,  # Store starting directory
            'created_at': datetime.now().isoformat(),
            'last_played': None,
            'play_count': 0
        }
        
        self.recordings[recording_id] = recording
        self.save_recordings()
        return recording_id
    
    def get_recording(self, recording_id):
        """Get a recording by ID"""
        return self.recordings.get(recording_id)
    
    def get_all_recordings(self):
        """Get all recordings sorted by creation date (most recent first)"""
        recordings_list = list(self.recordings.values())
        recordings_list.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        return recordings_list
    
    def update_recording(self, recording_id, name=None, commands=None, description=None):
        """Update an existing recording"""
        if recording_id not in self.recordings:
            return False
        
        recording = self.recordings[recording_id]
        
        if name is not None:
            recording['name'] = name
        if commands is not None:
            # Normalize commands to dict format
            normalized_commands = []
            for cmd in commands:
                if isinstance(cmd, str):
                    normalized_commands.append({'command': cmd, 'directory': None})
                elif isinstance(cmd, dict):
                    normalized_commands.append({
                        'command': cmd.get('command', ''),
                        'directory': cmd.get('directory')
                    })
                else:
                    normalized_commands.append({'command': str(cmd), 'directory': None})
            recording['commands'] = normalized_commands
        if description is not None:
            recording['description'] = description
        
        self.save_recordings()
        return True
    
    def delete_recording(self, recording_id):
        """Delete a recording"""
        if recording_id in self.recordings:
            del self.recordings[recording_id]
            self.save_recordings()
            return True
        return False
    
    def track_play(self, recording_id):
        """Track that a recording was played"""
        if recording_id in self.recordings:
            self.recordings[recording_id]['play_count'] += 1
            self.recordings[recording_id]['last_played'] = datetime.now().isoformat()
            self.save_recordings()
    
    def duplicate_recording(self, recording_id):
        """Create a duplicate of an existing recording"""
        if recording_id not in self.recordings:
            return None
        
        original = self.recordings[recording_id]
        new_name = f"{original['name']} (Copy)"
        
        return self.create_recording(
            new_name,
            original['commands'].copy(),
            original.get('description', '')
        )
    
    def export_recording(self, recording_id, file_path):
        """Export a recording to a JSON file"""
        if recording_id not in self.recordings:
            return False
        
        try:
            recording = self.recordings[recording_id]
            with open(file_path, 'w') as f:
                json.dump(recording, f, indent=2)
            return True
        except Exception as e:
            return False
    
    def import_recording(self, file_path):
        """Import a recording from a JSON file"""
        try:
            with open(file_path, 'r') as f:
                recording = json.load(f)
            
            # Generate new ID
            recording_id = f"recording_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            recording['id'] = recording_id
            recording['created_at'] = datetime.now().isoformat()
            recording['play_count'] = 0
            recording['last_played'] = None
            
            # Normalize commands format
            if 'commands' in recording:
                normalized_commands = []
                for cmd in recording['commands']:
                    if isinstance(cmd, str):
                        normalized_commands.append({'command': cmd, 'directory': None})
                    elif isinstance(cmd, dict):
                        normalized_commands.append({
                            'command': cmd.get('command', ''),
                            'directory': cmd.get('directory')
                        })
                    else:
                        normalized_commands.append({'command': str(cmd), 'directory': None})
                recording['commands'] = normalized_commands
            
            self.recordings[recording_id] = recording
            self.save_recordings()
            return recording_id
        except Exception as e:
            return None



