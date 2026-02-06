"""Command queue management with FIFO execution"""

from PyQt5.QtCore import QObject, pyqtSignal, QTimer
from collections import deque

class CommandQueue(QObject):
    """Manages a FIFO queue of commands for a specific terminal"""
    
    execute_command = pyqtSignal(str, dict, object)  # command, env_vars, terminal_widget
    queue_updated = pyqtSignal()
    
    def __init__(self, terminal_widget=None):
        super().__init__()
        self.terminal_widget = terminal_widget  # Reference to the terminal this queue belongs to
        self.queue = deque()
        self.is_running = False
        self.current_command = None
        self.waiting_for_completion = False  # Track if we're waiting for command to finish
        self.timeout_timer = QTimer()
        self.timeout_timer.setSingleShot(True)
        self.timeout_timer.timeout.connect(self._on_timeout)
        self.command_timeout_ms = 30000  # Default 30 seconds timeout for detecting long-running processes
        
    def add_command(self, command, name, env_vars=None):
        """Add a command to the queue"""
        item = {
            'command': command,
            'name': name,
            'env_vars': env_vars or {},
            'status': 'pending'
        }
        self.queue.append(item)
        self.queue_updated.emit()
        
        # If queue is running and not waiting for a command to complete, process immediately
        if self.is_running and not self.current_command and not self.waiting_for_completion:
            self.process_next()
    
    def set_timeout(self, timeout_ms):
        """Set the timeout for detecting long-running commands (in milliseconds)"""
        self.command_timeout_ms = timeout_ms
    
    def _on_timeout(self):
        """Handle command timeout - assume it's a long-running process and continue queue"""
        if self.current_command and self.waiting_for_completion:
            self.current_command['status'] = 'completed (timeout)'
            self.current_command = None  # Clear immediately
            self.waiting_for_completion = False
            self.queue_updated.emit()
            
            # Process next command if queue is running
            if self.is_running and self.queue:
                self.process_next()
    
    def start(self):
        """Start processing the queue"""
        self.is_running = True
        if self.queue and not self.current_command and not self.waiting_for_completion:
            self.process_next()
    
    def stop(self):
        """Stop processing the queue"""
        self.is_running = False
        self.timeout_timer.stop()
    
    def clear(self):
        """Clear all commands from queue"""
        self.queue.clear()
        self.current_command = None
        self.is_running = False
        self.waiting_for_completion = False
        self.timeout_timer.stop()
        self.queue_updated.emit()
    
    def process_next(self):
        """Process the next command in queue"""
        if not self.is_running or not self.queue or self.waiting_for_completion:
            return
        
        # Get next command
        self.current_command = self.queue.popleft()
        self.current_command['status'] = 'running'
        self.waiting_for_completion = True  # Mark that we're waiting for this command to finish
        self.queue_updated.emit()
        
        # Start timeout timer
        if self.command_timeout_ms > 0:
            self.timeout_timer.start(self.command_timeout_ms)
        
        # Execute command
        self.execute_command.emit(
            self.current_command['command'],
            self.current_command['env_vars'],
            self.terminal_widget
        )
        
        # Note: We wait for either on_command_complete to be called or timeout
    
    def on_command_complete(self):
        """Handle command completion - should be called when the terminal command finishes"""
        # Stop timeout timer since command completed normally
        self.timeout_timer.stop()
        
        if self.current_command:
            self.current_command['status'] = 'completed'
            self.current_command = None  # Clear immediately so it doesn't obstruct the queue view
            self.waiting_for_completion = False  # Reset waiting flag
            self.queue_updated.emit()  # Update display
            
            # Process next command if queue is running
            if self.is_running and self.queue and not self.waiting_for_completion:
                self.process_next()
    
    def force_complete_current(self):
        """Force the current command to complete and continue with next command"""
        if self.current_command and self.waiting_for_completion:
            self.timeout_timer.stop()
            self.current_command['status'] = 'completed (forced)'
            self.current_command = None  # Clear immediately
            self.waiting_for_completion = False
            self.queue_updated.emit()
            
            # Process next command if queue is running
            if self.is_running and self.queue:
                self.process_next()
            return True
        return False
    
    def get_queue(self):
        """Get all items in queue"""
        items = list(self.queue)
        if self.current_command:
            items.insert(0, self.current_command)
        return items
    
    def get_queue_size(self):
        """Get the number of items in queue"""
        size = len(self.queue)
        if self.current_command:
            size += 1
        return size
    
    def edit_command(self, index, new_command):
        """Edit a command in the queue"""
        if 0 <= index < len(self.queue):
            self.queue[index]['command'] = new_command
            self.queue_updated.emit()
            return True
        return False
    
    def remove_command(self, index):
        """Remove a command from the queue"""
        if 0 <= index < len(self.queue):
            del self.queue[index]
            self.queue_updated.emit()
            return True
        return False
    
    def move_command(self, from_index, to_index):
        """Move a command to a different position in queue"""
        if 0 <= from_index < len(self.queue) and 0 <= to_index < len(self.queue):
            item = self.queue[from_index]
            del self.queue[from_index]
            self.queue.insert(to_index, item)
            self.queue_updated.emit()
            return True
        return False
    
    def get_status(self):
        """Get status information for this queue
        
        Returns:
            dict: Status information including:
                - is_running: bool
                - queue_size: int (total including current)
                - pending_size: int (not including current)
                - current_command: dict or None
                - completed_count: int (estimated based on what's not in queue)
        """
        return {
            'is_running': self.is_running,
            'queue_size': self.get_queue_size(),
            'pending_size': len(self.queue),
            'current_command': self.current_command,
            'waiting_for_completion': self.waiting_for_completion
        }

