"""Session Recorder Widget for recording and playing back command sequences"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QListWidget, QListWidgetItem, QDialog,
                             QDialogButtonBox, QLineEdit, QTextEdit, QMessageBox,
                             QGroupBox, QScrollArea, QFrame, QMenu, QFileDialog,
                             QInputDialog)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QPalette
from core.session_recorder import SessionRecorder

class EditRecordingDialog(QDialog):
    """Dialog to edit/create a recording"""
    
    def __init__(self, parent=None, name="", commands=None, description=""):
        super().__init__(parent)
        self.setWindowTitle("Edit Recording" if name else "Create Recording")
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)
        self.init_ui(name, commands or [], description)
    
    def init_ui(self, name, commands, description):
        """Initialize the UI"""
        layout = QVBoxLayout(self)
        
        # Recording name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Recording Name:"))
        self.name_input = QLineEdit(name)
        self.name_input.setPlaceholderText("e.g., Deploy to Production")
        # Add error style for validation
        self.name_input.setStyleSheet("""
            QLineEdit {
                background-color: #3a3a3a;
                color: white;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 6px;
            }
            QLineEdit:focus {
                border: 1px solid #0d47a1;
            }
            QLineEdit[error="true"] {
                border: 2px solid #f44336;
                background-color: #4a2a2a;
            }
        """)
        name_layout.addWidget(self.name_input)
        layout.addLayout(name_layout)
        
        # Description
        layout.addWidget(QLabel("Description (optional):"))
        self.description_input = QLineEdit(description)
        self.description_input.setPlaceholderText("Brief description of this sequence")
        layout.addWidget(self.description_input)
        
        # Commands
        layout.addWidget(QLabel("Commands (one per line):"))
        self.commands_input = QTextEdit()
        # Handle both old format (strings) and new format (dicts with command and directory)
        if commands and len(commands) > 0:
            if isinstance(commands[0], dict):
                command_lines = []
                for cmd_data in commands:
                    cmd = cmd_data.get('command', '')
                    directory = cmd_data.get('directory')
                    if directory:
                        command_lines.append(f"# Directory: {directory}\n{cmd}")
                    else:
                        command_lines.append(cmd)
                self.commands_input.setPlainText('\n'.join(command_lines))
            else:
                self.commands_input.setPlainText('\n'.join(commands))
        else:
            self.commands_input.setPlainText('')
        self.commands_input.setPlaceholderText("Enter commands, one per line:\ncd /path/to/project\ngit pull\nnpm install\nnpm run build")
        self.commands_input.setFont(QFont("Courier New", 10))
        layout.addWidget(self.commands_input)
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.validate_and_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def validate_and_accept(self):
        """Validate the form before accepting"""
        name = self.name_input.text().strip()
        
        if not name:
            # Highlight the name input field
            self.name_input.setProperty("error", "true")
            self.name_input.style().unpolish(self.name_input)
            self.name_input.style().polish(self.name_input)
            self.name_input.setFocus()
            
            # Show error message
            QMessageBox.warning(
                self,
                "Name Required",
                "Please enter a name for this recording.\n\nThe name field has been highlighted."
            )
            return
        
        # Clear error state if name is valid
        self.name_input.setProperty("error", "false")
        self.name_input.style().unpolish(self.name_input)
        self.name_input.style().polish(self.name_input)
        
        # Accept the dialog
        self.accept()
    
    def get_data(self):
        """Get the dialog data"""
        commands_text = self.commands_input.toPlainText().strip()
        commands_lines = [cmd.strip() for cmd in commands_text.split('\n') if cmd.strip()]
        
        # Parse commands, handling directory comments
        commands = []
        current_directory = None
        for line in commands_lines:
            if line.startswith('# Directory:'):
                current_directory = line.replace('# Directory:', '').strip()
                if not current_directory or current_directory == 'None':
                    current_directory = None
            else:
                commands.append({
                    'command': line,
                    'directory': current_directory
                })
        
        return {
            'name': self.name_input.text().strip(),
            'description': self.description_input.text().strip(),
            'commands': commands if commands else []
        }


class SessionRecorderWidget(QWidget):
    """Widget for recording and playing back command sessions"""
    
    # Signals
    command_executed = pyqtSignal(str)  # Emits command to execute
    playback_started = pyqtSignal()
    playback_stopped = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.recorder = SessionRecorder()
        self.is_recording = False
        self.recorded_commands = []  # List of dicts: {'command': str, 'directory': str}
        self.recording_start_directory = None  # Starting directory when recording began
        self.current_tracked_directory = None  # Track current directory as commands are recorded
        self.is_playing = False
        self.is_paused = False
        self.current_playback_index = 0
        self.current_playback_id = None
        self.playback_timer = QTimer()
        self.playback_timer.timeout.connect(self.on_timer_timeout)
        self.current_terminal = None  # Reference to current terminal for prompt-based waiting
        self.current_command_directory = None  # Track directory for current command during playback
        self.current_command_index = -1  # Track which command is currently executing
        self.pending_command = None  # Command to execute after cd completes
        self.waiting_for_cd = False  # Flag to track if waiting for cd to complete
        self.init_ui()
        self.load_recordings()
    
    def init_ui(self):
        """Initialize the UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Header
        header = QLabel("🎬 Session Recorder")
        header.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                padding: 8px;
                background-color: #2b2b2b;
                color: #e0e0e0;
                border-radius: 4px;
            }
        """)
        layout.addWidget(header)
        
        # Recording Section
        recording_group = QGroupBox("Recording")
        recording_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #555;
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #2b2b2b;
                color: #e0e0e0;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        recording_layout = QVBoxLayout()
        
        # Recording status
        self.recording_status_label = QLabel("Not Recording")
        self.recording_status_label.setStyleSheet("""
            QLabel {
                padding: 8px;
                background-color: #1e1e1e;
                border: 1px solid #555;
                border-radius: 3px;
                color: #999;
                font-size: 12px;
            }
        """)
        recording_layout.addWidget(self.recording_status_label)
        
        # Help text
        help_text = QLabel("💡 Tip: Type commands directly in terminal or use Buttons/Command Book")
        help_text.setWordWrap(True)
        help_text.setStyleSheet("""
            QLabel {
                padding: 5px;
                color: #888;
                font-size: 10px;
                font-style: italic;
            }
        """)
        recording_layout.addWidget(help_text)
        
        # Recording buttons
        rec_buttons_layout = QHBoxLayout()
        
        self.start_recording_btn = QPushButton("⏺ Start Recording")
        self.start_recording_btn.clicked.connect(self.start_recording)
        self.start_recording_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 8px 12px;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:disabled {
                background-color: #2b2b2b;
                color: #666;
            }
        """)
        rec_buttons_layout.addWidget(self.start_recording_btn)
        
        self.stop_recording_btn = QPushButton("⏹ Stop Recording")
        self.stop_recording_btn.clicked.connect(self.stop_recording)
        self.stop_recording_btn.setEnabled(False)
        self.stop_recording_btn.setStyleSheet("""
            QPushButton {
                background-color: #424242;
                color: white;
                border: none;
                padding: 8px 12px;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #616161;
            }
            QPushButton:disabled {
                background-color: #2b2b2b;
                color: #666;
            }
        """)
        rec_buttons_layout.addWidget(self.stop_recording_btn)
        
        recording_layout.addLayout(rec_buttons_layout)
        
        # Command count during recording
        self.command_count_label = QLabel("Commands: 0")
        self.command_count_label.setStyleSheet("color: #999; font-size: 11px; padding: 5px;")
        recording_layout.addWidget(self.command_count_label)
        
        recording_group.setLayout(recording_layout)
        layout.addWidget(recording_group)
        
        # Recordings Library Section
        library_label = QLabel("Recordings Library")
        library_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                padding: 8px 5px 5px 5px;
                color: #e0e0e0;
            }
        """)
        layout.addWidget(library_label)
        
        # Toolbar for library
        library_toolbar = QHBoxLayout()
        
        import_btn = QPushButton("📥 Import")
        import_btn.clicked.connect(self.import_recording)
        import_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 6px 10px;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        library_toolbar.addWidget(import_btn)
        
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.load_recordings)
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #424242;
                color: white;
                border: none;
                padding: 6px 10px;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #616161;
            }
        """)
        library_toolbar.addWidget(refresh_btn)
        library_toolbar.addStretch()
        
        layout.addLayout(library_toolbar)
        
        # Recordings scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid #555;
                background-color: #1e1e1e;
                border-radius: 4px;
            }
        """)
        
        self.recordings_container = QWidget()
        self.recordings_layout = QVBoxLayout(self.recordings_container)
        self.recordings_layout.setAlignment(Qt.AlignTop)
        self.recordings_layout.setSpacing(5)
        
        scroll.setWidget(self.recordings_container)
        layout.addWidget(scroll)
    
    def get_current_terminal_directory(self):
        """Get the current working directory from the active terminal"""
        
        # Try current_terminal first - use current_directory attribute
        if self.current_terminal and hasattr(self.current_terminal, 'current_directory'):
            dir_result = self.current_terminal.current_directory
            return dir_result
        
        # Try to find the main window and get current terminal
        try:
            from PyQt5.QtWidgets import QApplication
            app = QApplication.instance()
            if app:
                widget_count = 0
                for widget in app.allWidgets():
                    if hasattr(widget, 'terminal_tabs'):
                        widget_count += 1
                        current_terminal = widget.terminal_tabs.get_current_terminal()
                        if current_terminal:
                            if hasattr(current_terminal, 'current_directory'):
                                dir_result = current_terminal.current_directory
                                return dir_result
                            else:
                                pass
                        else:
                            pass
        except Exception as e:
            import traceback
        
        # Fallback to current OS directory
        import os
        fallback_dir = os.getcwd()
        return fallback_dir
    
    def start_recording(self):
        """Start recording commands"""
        
        # Get current directory from terminal
        start_directory = self.get_current_terminal_directory()
        
        if start_directory:
            import os
            try:
                abs_path = os.path.abspath(os.path.expanduser(start_directory))
            except Exception as e:
                pass
        
        self.is_recording = True
        self.recorded_commands = []
        self.recording_start_directory = start_directory
        self.current_tracked_directory = start_directory  # Initialize tracked directory
        self.start_recording_btn.setEnabled(False)
        self.stop_recording_btn.setEnabled(True)
        self.recording_status_label.setText("🔴 Recording...")
        self.recording_status_label.setStyleSheet("""
            QLabel {
                padding: 8px;
                background-color: #1e1e1e;
                border: 1px solid #f44336;
                border-radius: 3px;
                color: #f44336;
                font-size: 12px;
                font-weight: bold;
            }
        """)
        self.update_command_count()
    
    def stop_recording(self):
        """Stop recording and prompt to save"""
        self.is_recording = False
        self.start_recording_btn.setEnabled(True)
        self.stop_recording_btn.setEnabled(False)
        self.recording_status_label.setText("Not Recording")
        self.recording_status_label.setStyleSheet("""
            QLabel {
                padding: 8px;
                background-color: #1e1e1e;
                border: 1px solid #555;
                border-radius: 3px;
                color: #999;
                font-size: 12px;
            }
        """)
        
        # Prompt to save if commands were recorded
        if self.recorded_commands:
            self.save_recording_dialog()
        else:
            QMessageBox.information(
                self,
                "No Commands Recorded",
                "No commands were recorded during this session.\n\n"
                "💡 Tip: To record commands:\n"
                "• Type commands directly in the terminal and press Enter\n"
                "• Use Command Buttons (in the Command Buttons tab)\n"
                "• Use Command Book (in the 📚 Book tab)\n"
                "• Use Command Queue (add commands to queue and run)\n\n"
                "Commands are automatically captured when you press Enter."
            )
        
        self.recorded_commands = []
        self.recording_start_directory = None
        self.current_tracked_directory = None
        self.update_command_count()
    
    def record_command(self, command, directory=None):
        """Record a command (called from external source)
        
        Args:
            command: The command string to record
            directory: Optional directory where the command was executed (before execution)
        """
        
        if self.is_recording:
            # Get the ACTUAL current directory from the terminal
            # This is the directory where the command will execute
            actual_current_dir = self.get_current_terminal_directory()
            
            command_stripped = command.strip()
            is_cd_command = command_stripped.startswith('cd ')
            
            # Always use the actual terminal directory for recording
            # This ensures we record where the command actually executes
            recorded_directory = actual_current_dir
            
            # After recording, update tracked directory for cd commands
            if is_cd_command:
                # Try to parse the cd target directory to update tracking
                cd_target = command_stripped[3:].strip()
                if cd_target:
                    import os
                    try:
                        # Resolve the cd target path
                        if cd_target.startswith('~'):
                            cd_target = os.path.expanduser(cd_target)
                        elif not os.path.isabs(cd_target):
                            # Relative path - resolve from current directory
                            if actual_current_dir:
                                cd_target = os.path.join(actual_current_dir, cd_target)
                            else:
                                cd_target = os.path.join(os.getcwd(), cd_target)
                        cd_target = os.path.abspath(cd_target)
                        
                        # Update tracked directory for next command
                        # Note: This is the EXPECTED directory after cd
                        # The actual terminal will update its directory when cd executes
                        if os.path.isdir(cd_target):
                            self.current_tracked_directory = cd_target
                        else:
                            pass
                    except Exception as e:
                        pass
            else:
                # For non-cd commands, update tracked directory to current actual directory
                if actual_current_dir:
                    self.current_tracked_directory = actual_current_dir
            
            # Record as dict with command and directory
            self.recorded_commands.append({
                'command': command,
                'directory': recorded_directory
            })
            for i, cmd_data in enumerate(self.recorded_commands, 1):
                dir_info = f" (dir: {cmd_data['directory']})" if cmd_data['directory'] else ""
            self.update_command_count()
        else:
            pass
    
    def update_command_count(self):
        """Update the command count label"""
        count = len(self.recorded_commands)
        self.command_count_label.setText(f"Commands: {count}")
    
    def save_recording_dialog(self):
        """Show dialog to save recording"""
        dialog = EditRecordingDialog(
            self,
            name="",
            commands=self.recorded_commands,
            description=""
        )
        
        if dialog.exec_():
            data = dialog.get_data()
            # Check if we have commands (handle both old string format and new dict format)
            has_commands = False
            if data.get('commands'):
                if isinstance(data['commands'], list):
                    if len(data['commands']) > 0:
                        # Check if it's list of strings or list of dicts
                        if isinstance(data['commands'][0], str):
                            has_commands = any(cmd.strip() for cmd in data['commands'])
                        else:
                            has_commands = any(cmd.get('command', '').strip() for cmd in data['commands'])
            
            if data['name'] and has_commands:
                pass
                
                recording_id = self.recorder.create_recording(
                    data['name'],
                    data['commands'],
                    data['description'],
                    self.recording_start_directory  # Pass starting directory
                )
                
                # Verify the recording was saved with start_directory
                saved_recording = self.recorder.get_recording(recording_id)
                if saved_recording:
                    saved_start_dir = saved_recording.get('start_directory')
                else:
                    pass
                
                
                self.load_recordings()
                QMessageBox.information(
                    self,
                    "Recording Saved",
                    f"Recording '{data['name']}' has been saved to the library."
                )
            else:
                # This shouldn't happen if validation works, but just in case
                QMessageBox.warning(
                    self,
                    "Invalid Input",
                    "Recording name and at least one command are required!"
                )
    
    def load_recordings(self):
        """Load and display all recordings"""
        # Clear existing recordings
        while self.recordings_layout.count():
            child = self.recordings_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # Load recordings
        recordings = self.recorder.get_all_recordings()
        
        if not recordings:
            no_recordings_label = QLabel("No recordings yet.\nStart recording to create one!")
            no_recordings_label.setAlignment(Qt.AlignCenter)
            no_recordings_label.setStyleSheet("""
                QLabel {
                    color: #999;
                    padding: 20px;
                    font-style: italic;
                }
            """)
            self.recordings_layout.addWidget(no_recordings_label)
        else:
            for recording in recordings:
                self.create_recording_widget(recording)
    
    def create_recording_widget(self, recording):
        """Create a widget for a recording"""
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: #2b2b2b;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 8px;
                margin: 2px;
            }
            QFrame:hover {
                border: 1px solid #4CAF50;
            }
        """)
        
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Recording name
        name_label = QLabel(recording['name'])
        name_label.setStyleSheet("""
            QLabel {
                font-size: 13px;
                font-weight: bold;
                color: #e0e0e0;
            }
        """)
        layout.addWidget(name_label)
        
        # Description (if present)
        if recording.get('description'):
            desc_label = QLabel(recording['description'])
            desc_label.setStyleSheet("""
                QLabel {
                    font-size: 11px;
                    color: #999;
                    font-style: italic;
                }
            """)
            desc_label.setWordWrap(True)
            layout.addWidget(desc_label)
        
        # Info line
        info_text = f"{len(recording['commands'])} commands"
        if recording.get('play_count', 0) > 0:
            info_text += f" • Played {recording['play_count']} times"
        
        info_label = QLabel(info_text)
        info_label.setStyleSheet("""
            QLabel {
                font-size: 10px;
                color: #666;
                padding: 2px 0;
            }
        """)
        layout.addWidget(info_label)
        
        # Buttons
        buttons_layout = QHBoxLayout()
        
        # Play button
        play_btn = QPushButton("▶ Play")
        play_btn.clicked.connect(lambda: self.play_recording(recording['id']))
        play_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        buttons_layout.addWidget(play_btn)
        
        # Pause button (shown during playback)
        pause_btn = QPushButton("⏸ Pause")
        pause_btn.clicked.connect(self.pause_playback)
        pause_btn.setVisible(False)
        pause_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
        """)
        buttons_layout.addWidget(pause_btn)
        
        # Stop button (shown during playback)
        stop_btn = QPushButton("⏹ Stop")
        stop_btn.clicked.connect(self.stop_playback)
        stop_btn.setVisible(False)
        stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)
        buttons_layout.addWidget(stop_btn)
        
        # Edit button
        edit_btn = QPushButton("✏️")
        edit_btn.setMaximumWidth(40)
        edit_btn.clicked.connect(lambda: self.edit_recording(recording['id']))
        edit_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 6px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        buttons_layout.addWidget(edit_btn)
        
        # More options button
        more_btn = QPushButton("⋮")
        more_btn.setMaximumWidth(40)
        more_btn.clicked.connect(lambda: self.show_recording_menu(recording['id'], more_btn))
        more_btn.setStyleSheet("""
            QPushButton {
                background-color: #424242;
                color: white;
                border: none;
                padding: 6px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #616161;
            }
        """)
        buttons_layout.addWidget(more_btn)
        
        layout.addLayout(buttons_layout)
        
        # Store references for playback control
        frame.setProperty('recording_id', recording['id'])
        frame.setProperty('play_btn', play_btn)
        frame.setProperty('pause_btn', pause_btn)
        frame.setProperty('stop_btn', stop_btn)
        
        self.recordings_layout.addWidget(frame)
    
    def play_recording(self, recording_id):
        """Start playing a recording"""
        
        if self.is_playing:
            QMessageBox.warning(
                self,
                "Already Playing",
                "Another recording is currently playing. Please stop it first."
            )
            return
        
        recording = self.recorder.get_recording(recording_id)
        if not recording:
            return
        
        for i, cmd in enumerate(recording['commands'], 1):
            if isinstance(cmd, dict):
                dir_info = f" [dir: {cmd.get('directory')}]" if cmd.get('directory') else " [no dir]"
            else:
                pass
        
        # Get the play directory (directory where the FIRST command was executed)
        play_directory = None
        commands = recording.get('commands', [])
        first_command_data = None
        first_command_str = None
        
        if commands and len(commands) > 0:
            first_command_data = commands[0]
            if isinstance(first_command_data, dict):
                play_directory = first_command_data.get('directory')
                first_command_str = first_command_data.get('command', '')
            else:
                # Old format (string)
                first_command_str = str(first_command_data)
                # Try to get from start_directory as fallback
                if recording.get('start_directory'):
                    play_directory = recording.get('start_directory')
        
        
        
        # Get current directory from terminal
        current_directory = self.get_current_terminal_directory()
        
        # Validate directory match - check if current directory matches play directory
        if play_directory:
            # Normalize paths for comparison (resolve symlinks, etc.)
            import os
            try:
                play_path = os.path.abspath(os.path.expanduser(play_directory))
                current_path = os.path.abspath(os.path.expanduser(current_directory))
                
                
                if play_path != current_path:
                    pass
                    
                    # Show error dialog with option to jump to directory
                    first_cmd = first_command_str if first_command_str else "N/A"
                    msg_box = QMessageBox(self)
                    msg_box.setIcon(QMessageBox.Critical)
                    msg_box.setWindowTitle("Directory Mismatch - Playback Blocked")
                    msg_box.setText("Cannot play recording: You are not in the correct directory.")
                    msg_box.setInformativeText(
                        f"📁 Play Directory (required):\n{play_path}\n\n"
                        f"📍 Current Directory:\n{current_path}\n\n"
                        f"First command '{first_cmd}' was executed in the play directory.\n"
                        f"You must be in the play directory to run this recording."
                    )
                    
                    # Add custom buttons
                    jump_btn = msg_box.addButton("Jump to Directory", QMessageBox.ActionRole)
                    cancel_btn = msg_box.addButton("Cancel", QMessageBox.RejectRole)
                    msg_box.setDefaultButton(jump_btn)
                    
                    # Show dialog
                    reply = msg_box.exec_()
                    
                    if reply == 0:  # Jump to Directory button clicked
                        
                        # Change terminal directory
                        terminal = self.current_terminal
                        if not terminal:
                            # Try to get terminal from main window
                            try:
                                from PyQt5.QtWidgets import QApplication
                                app = QApplication.instance()
                                if app:
                                    for widget in app.allWidgets():
                                        if hasattr(widget, 'terminal_tabs'):
                                            terminal = widget.terminal_tabs.get_current_terminal()
                                            break
                            except Exception as e:
                                pass
                        
                        if terminal:
                            # Change directory by executing cd command
                            cd_command = f"cd {play_path}"
                            if hasattr(terminal, 'execute_command'):
                                pass
                                
                                # Connect to prompt_ready signal to know when cd completes
                                def on_cd_complete():
                                    try:
                                        if hasattr(terminal, 'prompt_ready'):
                                            terminal.prompt_ready.disconnect(on_cd_complete)
                                        # Retry playback after cd completes
                                        self.play_recording(recording_id)
                                    except Exception as e:
                                        pass
                                
                                # Connect to prompt_ready signal if available
                                if hasattr(terminal, 'prompt_ready'):
                                    terminal.prompt_ready.connect(on_cd_complete)
                                    terminal.execute_command(cd_command)
                                else:
                                    # Fallback: use timer if prompt_ready signal not available
                                    from PyQt5.QtCore import QTimer
                                    terminal.execute_command(cd_command)
                                    QTimer.singleShot(500, on_cd_complete)
                                return
                            else:
                                QMessageBox.warning(
                                    self,
                                    "Cannot Change Directory",
                                    f"Could not change directory. Please manually navigate to:\n{play_path}"
                                )
                        else:
                            QMessageBox.warning(
                                self,
                                "No Terminal Found",
                                f"Could not find terminal to change directory. Please manually navigate to:\n{play_path}"
                            )
                    
                    return
                else:
                    pass
            except Exception as e:
                import traceback
                # On error, still block playback for safety
                QMessageBox.critical(
                    self,
                    "Directory Validation Error",
                    f"Error validating directory: {e}\n\nPlayback has been cancelled for safety."
                )
                return
        else:
            pass
        
        self.is_playing = True
        self.is_paused = False
        self.current_playback_index = 0
        self.current_playback_id = recording_id
        
        
        # Track play count
        self.recorder.track_play(recording_id)
        
        # Update UI
        self.update_playback_ui(recording_id, playing=True)
        
        # Start playback
        self.playback_started.emit()
        
        # Wait for terminal to be set (via on_playback_started callback)
        # The terminal will be set by main_window.on_playback_started()
        # We use a small delay to ensure the terminal is set before executing
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(50, self.setup_playback_and_start)
    
    def setup_playback_and_start(self):
        """Setup command_finished connection and start executing commands"""
        
        # Connect to command_finished signal once for error detection
        if self.current_terminal and hasattr(self.current_terminal, 'command_finished'):
            try:
                # Disconnect any existing connection first
                try:
                    self.current_terminal.command_finished.disconnect(self.on_command_finished)
                except:
                    pass
                # Connect to monitor command completion and errors
                self.current_terminal.command_finished.connect(self.on_command_finished)
            except Exception as e:
                pass
        
        # Start executing commands
        self.execute_next_command()
    
    def pause_playback(self):
        """Pause/resume playback"""
        if self.is_paused:
            self.is_paused = False
            self.execute_next_command()
        else:
            self.is_paused = True
            self.playback_timer.stop()
    
    def stop_playback(self):
        """Stop playback"""
        
        self.is_playing = False
        self.is_paused = False
        self.playback_timer.stop()
        
        # Disconnect from terminal's signals
        if self.current_terminal:
            if hasattr(self.current_terminal, 'prompt_ready'):
                try:
                    self.current_terminal.prompt_ready.disconnect(self.on_prompt_ready)
                except Exception as e:
                    pass
            
            if hasattr(self.current_terminal, 'command_finished'):
                try:
                    self.current_terminal.command_finished.disconnect(self.on_command_finished)
                except Exception as e:
                    pass
        else:
            pass
        
        if self.current_playback_id:
            self.update_playback_ui(self.current_playback_id, playing=False)
        
        self.current_playback_id = None
        self.current_playback_index = 0
        self.current_command_index = -1
        self.current_command_directory = None
        self.pending_command = None
        self.waiting_for_cd = False
        self.playback_stopped.emit()
    
    def set_current_terminal(self, terminal):
        """Set the current terminal widget for prompt-based waiting"""
        
        # Disconnect old terminal if connected
        if self.current_terminal and hasattr(self.current_terminal, 'prompt_ready'):
            try:
                self.current_terminal.prompt_ready.disconnect(self.on_prompt_ready)
            except Exception as e:
                pass
        
        # Set new terminal
        self.current_terminal = terminal
        
        # Connect to new terminal if playing
        if self.is_playing and self.current_terminal and hasattr(self.current_terminal, 'prompt_ready'):
            try:
                self.current_terminal.prompt_ready.connect(self.on_prompt_ready)
            except Exception as e:
                pass
        else:
            pass
        
    
    def execute_next_command(self):
        """Execute the next command in the playback sequence"""
        
        if not self.is_playing or self.is_paused:
            return
        
        recording = self.recorder.get_recording(self.current_playback_id)
        if not recording:
            self.stop_playback()
            return
        
        commands = recording['commands']
        
        if self.current_playback_index >= len(commands):
            # Finished playing
            self.stop_playback()
            QMessageBox.information(
                self,
                "Playback Complete",
                f"Recording '{recording['name']}' has finished playing."
            )
            return
        
        # Execute current command
        command_data = commands[self.current_playback_index]
        if isinstance(command_data, str):
            # Backward compatibility: old format (string)
            command = command_data
            directory = None
        else:
            # New format: dict with command and directory
            command = command_data.get('command', '')
            directory = command_data.get('directory')
        
        # Store current command info for error tracking
        self.current_command_index = self.current_playback_index
        self.current_command_directory = directory
        
        
        # Get current directory to see if we need to cd
        current_dir = self.get_current_terminal_directory()
        
        # Check if command is a cd command
        command_stripped = command.strip()
        is_cd_command = command_stripped.startswith('cd ')
        
        
        # If we have a target directory and we're not already there, change directory first
        # But skip if the command itself is a cd command (it will handle the directory change)
        if directory and not is_cd_command:
            # Normalize paths for comparison
            import os
            try:
                target_path = os.path.abspath(os.path.expanduser(directory))
                current_path = os.path.abspath(os.path.expanduser(current_dir))
                
                if target_path != current_path:
                    # Need to change directory first
                    cd_command = f"cd {directory}"
                    self.command_executed.emit(cd_command)
                    # Store the actual command to execute after cd
                    self.pending_command = command
                    self.waiting_for_cd = True
                else:
                    # Already in the correct directory
                    self.command_executed.emit(command)
                    self.pending_command = None
                    self.waiting_for_cd = False
            except Exception as e:
                self.command_executed.emit(command)
                self.pending_command = None
                self.waiting_for_cd = False
        else:
            # No directory specified or it's a cd command - execute directly
            self.command_executed.emit(command)
            self.pending_command = None
            self.waiting_for_cd = False
        
        
        # Move to next command index (but don't execute yet - wait for completion/error)
        old_index = self.current_playback_index
        self.current_playback_index += 1
        
        # Wait for prompt instead of using fixed delay
        # The prompt_ready signal will trigger execute_next_command again
        # If no terminal is available, fall back to timer
        
        if self.current_terminal and hasattr(self.current_terminal, 'prompt_ready'):
            # Wait for prompt - prompt_ready signal will call execute_next_command
            
            # Ensure we're connected to prompt_ready signal
            try:
                # Try to disconnect first (in case already connected)
                try:
                    self.current_terminal.prompt_ready.disconnect(self.on_prompt_ready)
                except:
                    pass  # Not connected, that's fine
                
                # Connect to signal
                self.current_terminal.prompt_ready.connect(self.on_prompt_ready)
            except Exception as e:
                self.playback_timer.start(1000)
            
        else:
            # Fallback: use timer if terminal doesn't support prompt-based waiting
            self.playback_timer.start(1000)
        
    
    def on_timer_timeout(self):
        """Called when timer expires - continue with next command"""
        self.execute_next_command()
    
    def on_command_finished(self, exit_code):
        """Called when a command finishes - check for errors"""
        
        # Check for error (non-zero exit code)
        if exit_code != 0:
            pass
            
            # Get command details for error message
            recording = self.recorder.get_recording(self.current_playback_id)
            if recording:
                commands = recording['commands']
                if 0 <= self.current_command_index < len(commands):
                    command_data = commands[self.current_command_index]
                    if isinstance(command_data, dict):
                        command = command_data.get('command', '')
                        directory = command_data.get('directory')
                    else:
                        command = str(command_data)
                        directory = None
                    
                    # If we were waiting for cd, the error is from cd
                    if self.waiting_for_cd:
                        error_cmd = f"cd {directory}"
                        error_msg = f"Failed to change directory during playback:\n\nCommand: {error_cmd}\nDirectory: {directory}\nExit Code: {exit_code}\n\nPlayback has been stopped."
                    else:
                        error_cmd = command
                        dir_info = f"\nDirectory: {directory}" if directory else ""
                        error_msg = f"Command execution failed during playback:\n\nCommand: {error_cmd}{dir_info}\nExit Code: {exit_code}\n\nPlayback has been stopped."
                    
                    # Stop playback
                    self.stop_playback()
                    
                    # Show error message
                    QMessageBox.critical(
                        self,
                        "Playback Error",
                        error_msg
                    )
                    return
        
        # If we were waiting for cd to complete, now execute the actual command
        if self.waiting_for_cd and self.pending_command:
            # Update our tracked directory after cd completed
            if self.current_command_directory:
                # The cd command changed us to this directory
                import os
                try:
                    new_dir = os.path.abspath(os.path.expanduser(self.current_command_directory))
                except:
                    pass
            
            self.waiting_for_cd = False
            # Execute the pending command
            QTimer.singleShot(50, lambda: self.command_executed.emit(self.pending_command))
            self.pending_command = None
            # Don't continue to next command yet - wait for this command to finish
            return
        
        # Handle cd commands - update tracked directory
        recording = self.recorder.get_recording(self.current_playback_id)
        if recording and 0 <= self.current_command_index < len(recording['commands']):
            command_data = recording['commands'][self.current_command_index]
            if isinstance(command_data, dict):
                command = command_data.get('command', '')
                if command.strip().startswith('cd '):
                    # Update tracked directory after cd
                    directory = command_data.get('directory')
                    if directory:
                        import os
                        try:
                            # Resolve the cd target
                            cd_target = command.strip()[3:].strip()
                            if cd_target:
                                if cd_target.startswith('~'):
                                    cd_target = os.path.expanduser(cd_target)
                                elif not os.path.isabs(cd_target):
                                    # Relative path
                                    current_dir = self.get_current_terminal_directory()
                                    if current_dir:
                                        cd_target = os.path.join(current_dir, cd_target)
                                cd_target = os.path.abspath(cd_target)
                        except Exception as e:
                            pass
        
        # Command succeeded - continue with prompt-based waiting
    
    def on_prompt_ready(self):
        """Called when a new prompt appears - continue with next command"""
        self.execute_next_command()
    
    def update_playback_ui(self, recording_id, playing=False):
        """Update UI to show/hide playback controls"""
        for i in range(self.recordings_layout.count()):
            widget = self.recordings_layout.itemAt(i).widget()
            if widget and isinstance(widget, QFrame):
                widget_id = widget.property('recording_id')
                if widget_id == recording_id:
                    play_btn = widget.property('play_btn')
                    pause_btn = widget.property('pause_btn')
                    stop_btn = widget.property('stop_btn')
                    
                    if play_btn and pause_btn and stop_btn:
                        play_btn.setVisible(not playing)
                        pause_btn.setVisible(playing)
                        stop_btn.setVisible(playing)
    
    def edit_recording(self, recording_id):
        """Edit a recording"""
        recording = self.recorder.get_recording(recording_id)
        if not recording:
            return
        
        dialog = EditRecordingDialog(
            self,
            name=recording['name'],
            commands=recording['commands'],
            description=recording.get('description', '')
        )
        
        if dialog.exec_():
            data = dialog.get_data()
            # Check if we have commands (handle both old string format and new dict format)
            has_commands = False
            if data.get('commands'):
                if isinstance(data['commands'], list):
                    if len(data['commands']) > 0:
                        # Check if it's list of strings or list of dicts
                        if isinstance(data['commands'][0], str):
                            has_commands = any(cmd.strip() for cmd in data['commands'])
                        else:
                            has_commands = any(cmd.get('command', '').strip() for cmd in data['commands'])
            
            if data['name'] and has_commands:
                self.recorder.update_recording(
                    recording_id,
                    name=data['name'],
                    commands=data['commands'],
                    description=data['description']
                )
                self.load_recordings()
            else:
                # This shouldn't happen if validation works, but just in case
                QMessageBox.warning(
                    self,
                    "Invalid Input",
                    "Recording name and at least one command are required!"
                )
    
    def show_recording_menu(self, recording_id, button):
        """Show context menu for recording"""
        menu = QMenu(self)
        
        duplicate_action = menu.addAction("📋 Duplicate")
        duplicate_action.triggered.connect(lambda: self.duplicate_recording(recording_id))
        
        export_action = menu.addAction("💾 Export")
        export_action.triggered.connect(lambda: self.export_recording(recording_id))
        
        menu.addSeparator()
        
        delete_action = menu.addAction("🗑️ Delete")
        delete_action.triggered.connect(lambda: self.delete_recording(recording_id))
        
        # Show menu at button position
        menu.exec_(button.mapToGlobal(button.rect().bottomLeft()))
    
    def duplicate_recording(self, recording_id):
        """Duplicate a recording"""
        new_id = self.recorder.duplicate_recording(recording_id)
        if new_id:
            self.load_recordings()
            QMessageBox.information(
                self,
                "Recording Duplicated",
                "Recording has been duplicated successfully."
            )
    
    def export_recording(self, recording_id):
        """Export a recording to file"""
        recording = self.recorder.get_recording(recording_id)
        if not recording:
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Recording",
            f"{recording['name']}.json",
            "JSON Files (*.json)"
        )
        
        if file_path:
            if self.recorder.export_recording(recording_id, file_path):
                QMessageBox.information(
                    self,
                    "Export Successful",
                    f"Recording exported to:\n{file_path}"
                )
            else:
                QMessageBox.warning(
                    self,
                    "Export Failed",
                    "Failed to export recording."
                )
    
    def import_recording(self):
        """Import a recording from file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Recording",
            "",
            "JSON Files (*.json)"
        )
        
        if file_path:
            recording_id = self.recorder.import_recording(file_path)
            if recording_id:
                self.load_recordings()
                QMessageBox.information(
                    self,
                    "Import Successful",
                    "Recording has been imported successfully."
                )
            else:
                QMessageBox.warning(
                    self,
                    "Import Failed",
                    "Failed to import recording."
                )
    
    def delete_recording(self, recording_id):
        """Delete a recording"""
        recording = self.recorder.get_recording(recording_id)
        if not recording:
            return
        
        reply = QMessageBox.question(
            self,
            "Delete Recording",
            f"Are you sure you want to delete '{recording['name']}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.recorder.delete_recording(recording_id)
            self.load_recordings()

