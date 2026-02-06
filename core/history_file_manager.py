"""History file manager for terminal output archival with streaming detection"""

import os
import json
import gzip
import time
from datetime import datetime
from pathlib import Path


class HistoryFileManager:
    """Manages compressed history files for terminal tabs"""
    
    def __init__(self):
        # Create history directory if it doesn't exist
        self.history_dir = Path.home() / '.terminal_browser' / 'history'
        self.history_dir.mkdir(parents=True, exist_ok=True)
        
        # Track active history files by tab_id
        self._active_files = {}  # {tab_id: file_path}
        self._file_data = {}  # {tab_id: history_data_dict}
    
    def create_history_file(self, tab_id):
        """
        Create a new history file for a tab
        
        Args:
            tab_id: Unique identifier for the terminal tab
            
        Returns:
            str: Path to the created history file
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"terminal_history_{tab_id}_{timestamp}.tbhist"
        file_path = self.history_dir / filename
        
        # Initialize file structure
        history_data = {
            "version": "1.0",
            "tab_id": tab_id,
            "created_at": datetime.now().isoformat(),
            "archives": [],
            "streaming_events": []
        }
        
        # Save initial structure
        self._save_compressed(file_path, history_data)
        
        # Track this file
        self._active_files[tab_id] = str(file_path)
        self._file_data[tab_id] = history_data
        
        return str(file_path)
    
    def get_history_file_path(self, tab_id):
        """Get the path to a tab's history file"""
        return self._active_files.get(tab_id)
    
    def replace_history_file(self, tab_id, lines_data, command_context=None):
        """
        Replace/create history file with current terminal content (single archive approach)
        
        Args:
            tab_id: Terminal tab identifier
            lines_data: List of line dictionaries with content and color info
            command_context: Command that generated this output
            
        Returns:
            str: Path to the history file
        """
        # Create new timestamp for this snapshot
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"terminal_history_{tab_id}_{timestamp}.tbhist"
        file_path = self.history_dir / filename
        
        # Create single archive entry with all content
        history_data = {
            "version": "1.0",
            "tab_id": tab_id,
            "created_at": datetime.now().isoformat(),
            "command_context": command_context or "clear",
            "total_lines": len(lines_data),
            "lines": lines_data
        }
        
        # Save the file
        self._save_compressed(file_path, history_data)
        
        # Update tracking (remove old file reference)
        old_file = self._active_files.get(tab_id)
        self._active_files[tab_id] = str(file_path)
        self._file_data[tab_id] = history_data
        
        return str(file_path)
    
    def append_archive(self, tab_id, lines_data, row_range, command_context=None):
        """
        Append archived lines to EXISTING history file (continuous append mode)
        
        Args:
            tab_id: Terminal tab identifier
            lines_data: List of line dictionaries with content and color info
            row_range: String like "0-500" or "auto-archive-5000-lines"
            command_context: Command that generated this output
        """
        print(f"\n[DEBUG] append_archive called: tab_id={tab_id}, row_range={row_range}, context={command_context}, lines={len(lines_data)}")
        print(f"[DEBUG] append_archive: _active_files keys: {list(self._active_files.keys())}")
        print(f"[DEBUG] append_archive: tab_id in _active_files? {tab_id in self._active_files}")
        
        # Ensure history file exists
        if tab_id not in self._active_files:
            print(f"[DEBUG] append_archive: No file for tab_id '{tab_id}', creating new one")
            print(f"[DEBUG] append_archive: Available tab_ids: {list(self._active_files.keys())}")
            self.create_history_file(tab_id)
        
        # Load current data from file (always reload to get latest)
        file_path = self._active_files[tab_id]
        print(f"[DEBUG] append_archive: Using file: {file_path}")
        print(f"[DEBUG] append_archive: Loading from file: {file_path}")
        
        try:
            history_data = self._load_compressed(file_path)
        except Exception as e:
            # If file is corrupted or doesn't exist, recreate it
            print(f"[DEBUG] Error loading history file, recreating: {e}")
            self.create_history_file(tab_id)
            history_data = self._load_compressed(file_path)
        
        # Ensure archives array exists (safety check)
        if "archives" not in history_data:
            print(f"[DEBUG] append_archive: No 'archives' key, adding empty array")
            history_data["archives"] = []
        
        current_archive_count = len(history_data["archives"])
        print(f"[DEBUG] append_archive: Current archive count BEFORE append: {current_archive_count}")
        
        # Create archive entry with line count
        archive_entry = {
            "timestamp": datetime.now().isoformat(),
            "row_range": row_range,
            "command_context": command_context or "Unknown",
            "lines": lines_data,
            "line_count": len(lines_data)
        }
        
        # APPEND to archives array (not replace)
        history_data["archives"].append(archive_entry)
        
        new_archive_count = len(history_data["archives"])
        print(f"[DEBUG] append_archive: Archive count AFTER append: {new_archive_count}")
        
        # Update metadata
        history_data["last_updated"] = datetime.now().isoformat()
        history_data["total_archives"] = len(history_data["archives"])
        
        print(f"[DEBUG] append_archive: Saving to file with {new_archive_count} archives")
        # Save updated data back to SAME file
        self._save_compressed(file_path, history_data)
        
        # Update in-memory cache
        self._file_data[tab_id] = history_data
        print(f"[DEBUG] append_archive: Complete. File now has {new_archive_count} archives\n")
    
    def append_streaming_marker(self, tab_id, marker_type, timestamp, duration=None):
        """
        Add streaming state marker to history file
        
        Args:
            tab_id: Terminal tab identifier
            marker_type: "stopped" or "resumed"
            timestamp: ISO format timestamp
            duration: For "stopped", pause duration in seconds
        """
        # Ensure history file exists
        if tab_id not in self._active_files:
            self.create_history_file(tab_id)
        
        # Load current data
        file_path = self._active_files[tab_id]
        if tab_id not in self._file_data:
            self._file_data[tab_id] = self._load_compressed(file_path)
        
        history_data = self._file_data[tab_id]
        
        # Create streaming event
        event = {
            "event": marker_type,
            "timestamp": timestamp,
            "duration": duration
        }
        
        history_data["streaming_events"].append(event)
        
        # Create marker line for the last archive
        if history_data["archives"]:
            last_archive = history_data["archives"][-1]
            marker_line = {
                "row": len(last_archive["lines"]),
                "type": "streaming_marker",
                "marker_type": marker_type,
                "timestamp": timestamp,
                "pause_duration": duration,
                "content": self._format_marker_content(marker_type, duration, timestamp)
            }
            last_archive["lines"].append(marker_line)
        
        # Save updated data
        self._save_compressed(file_path, history_data)
    
    def _format_marker_content(self, marker_type, duration, timestamp):
        """Generate visual marker content"""
        dt = datetime.fromisoformat(timestamp)
        time_str = dt.strftime('%Y-%m-%d %H:%M:%S')
        
        if marker_type == "stopped":
            duration_str = f"{duration:.1f}s" if duration else "unknown"
            return (
                "\n" +
                "|||||||||||||||||||||||||||||||||||||||||||||||||||||||||\n" +
                f"⏸ Streaming paused ({duration_str} gap detected)\n" +
                f"   Stopped at: {time_str}\n" +
                "|||||||||||||||||||||||||||||||||||||||||||||||||||||||||\n"
            )
        elif marker_type == "resumed":
            return (
                "|||||||||||||||||||||||||||||||||||||||||||||||||||||||||\n" +
                "▶ Streaming resumed\n" +
                f"   Resumed at: {time_str}\n" +
                "|||||||||||||||||||||||||||||||||||||||||||||||||||||||||\n"
            )
        return ""
    
    def get_file_size(self, tab_id):
        """
        Get formatted file size
        
        Returns:
            str: Formatted size like "12MB", "1.5GB", or "0B"
        """
        if tab_id not in self._active_files:
            return "0B"
        
        file_path = self._active_files[tab_id]
        if not os.path.exists(file_path):
            return "0B"
        
        size_bytes = os.path.getsize(file_path)
        return self._format_file_size(size_bytes)
    
    def _format_file_size(self, size_bytes):
        """Format bytes to human-readable size"""
        if size_bytes < 1024:
            return f"{size_bytes}B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f}KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f}MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f}GB"
    
    def load_history(self, file_path):
        """
        Load and decompress history file
        
        Args:
            file_path: Path to .tbhist file
            
        Returns:
            dict: Decompressed history data
        """
        return self._load_compressed(file_path)
    
    def import_history(self, file_path, target_tab_id):
        """
        Import history from file into a tab
        
        Args:
            file_path: Path to .tbhist file to import
            target_tab_id: Tab to import into
            
        Returns:
            dict: Imported history data
        """
        # Load the import file
        imported_data = self._load_compressed(file_path)
        
        # Validate format
        if not self._validate_history_file(imported_data):
            raise ValueError("Invalid history file format")
        
        # If target tab doesn't have history, create it
        if target_tab_id not in self._active_files:
            self.create_history_file(target_tab_id)
        
        # Load current history
        target_file = self._active_files[target_tab_id]
        target_data = self._file_data.get(target_tab_id) or self._load_compressed(target_file)
        
        # Merge archives
        target_data["archives"].extend(imported_data["archives"])
        target_data["streaming_events"].extend(imported_data.get("streaming_events", []))
        
        # Save merged data
        self._save_compressed(target_file, target_data)
        self._file_data[target_tab_id] = target_data
        
        return target_data
    
    def delete_history_file(self, tab_id):
        """
        Delete history file for a tab
        
        Args:
            tab_id: Terminal tab identifier
        """
        if tab_id in self._active_files:
            file_path = self._active_files[tab_id]
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as e:
                    pass
            
            # Clean up tracking
            del self._active_files[tab_id]
            if tab_id in self._file_data:
                del self._file_data[tab_id]
    
    def _save_compressed(self, file_path, data):
        """Save data as compressed JSON"""
        json_str = json.dumps(data, indent=2)
        with gzip.open(file_path, 'wt', encoding='utf-8') as f:
            f.write(json_str)
    
    def _load_compressed(self, file_path):
        """Load compressed JSON data"""
        try:
            with gzip.open(file_path, 'rt', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            return {
                "version": "1.0",
                "tab_id": "unknown",
                "created_at": datetime.now().isoformat(),
                "archives": [],
                "streaming_events": []
            }
    
    def _validate_history_file(self, data):
        """Validate history file structure"""
        required_keys = ["version", "tab_id", "archives"]
        return all(key in data for key in required_keys)
    
    def list_history_files(self):
        """List all available history files"""
        history_files = []
        for file_path in self.history_dir.glob("*.tbhist"):
            try:
                data = self._load_compressed(file_path)
                history_files.append({
                    "path": str(file_path),
                    "tab_id": data.get("tab_id", "unknown"),
                    "created_at": data.get("created_at"),
                    "size": self._format_file_size(os.path.getsize(file_path)),
                    "archives_count": len(data.get("archives", []))
                })
            except Exception as e:
                pass
        
        return history_files
