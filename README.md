# Terminal Browser 🚀

[![Python](https://img.shields.io/badge/Python-3.7+-blue.svg)](https://www.python.org/)
[![PyQt5](https://img.shields.io/badge/GUI-PyQt5-green.svg)](https://www.riverbankcomputing.com/software/pyqt/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A powerful desktop terminal application with browser-like tabs, terminal groups, and command execution management. Built for developers, system administrators, and DevOps professionals who need to manage multiple terminal sessions efficiently.

![Terminal Browser Banner](https://img.shields.io/badge/Terminal-Browser-4CAF50?style=for-the-badge)

---

## 📑 Table of Contents

- [Features](#-features)
  - [Terminal Management](#terminal-management)
  - [Command Buttons](#command-buttons)
  - [Command Queue](#command-queue)
  - [Session Recording & Playback](#-session-recording--playback)
  - [File Attachments](#file-attachments)
  - [Modern UI](#modern-ui)
- [Installation](#-installation)
  - [Prerequisites](#prerequisites)
  - [Quick Setup](#quick-setup)
  - [Building macOS App](#building-macos-app)
- [Getting Started](#-getting-started)
  - [Launching](#launching-the-application)
  - [Creating Groups](#creating-terminal-groups)
  - [Managing Tabs](#managing-terminal-tabs)
  - [Creating Buttons](#creating-command-buttons)
- [Usage Guide](#-usage-guide)
  - [Terminal Groups](#terminal-groups)
  - [Command Execution](#command-execution)
  - [File Management](#file-management)
  - [Preferences](#preferences)
- [Keyboard Shortcuts](#-keyboard-shortcuts)
  - [File Operations](#file-operations)
  - [Editing & Clipboard](#editing--clipboard)
  - [View & Zoom](#view--zoom)
  - [Terminal Control](#terminal-control)
- [Advanced Features](#-advanced-features)
  - [Command Queue Management](#command-queue-management)
  - [Environment Variables](#environment-variables)
  - [State Persistence](#state-persistence)
- [Use Cases](#-use-cases)
- [Troubleshooting](#-troubleshooting)
- [Project Structure](#-project-structure)
- [Contributing](#-contributing)
- [License](#-license)
- [Support](#-support)

---

## ✨ Features

### Terminal Management

#### 🖥️ Browser-Like Tabs
- **Horizontal Scrollable Tabs**: Navigate through multiple terminals with ease
- **Drag & Drop Reordering**: Organize tabs by dragging them to new positions
- **Tab Navigation Buttons**: Left/right arrows with hidden tab counts
- **Right-Click Context Menu**: Rename or close tabs quickly
- **Shell Selection**: Choose from bash, zsh, fish, and other available shells
- **Tab Indicators**: Each tab shows the active shell type

#### 📁 Terminal Groups
- **Logical Organization**: Group terminals by project, environment, or task
- **Independent Settings**: Each group maintains its own tabs, buttons, and files
- **Quick Switching**: Click any group to instantly switch between workspaces
- **Persistent Storage**: Groups and their contents are saved between sessions
- **Rename & Delete**: Easily manage group names and remove unused groups

#### 🎨 Full Terminal Emulation
- **Complete VT100/ANSI Support**: Full compatibility with terminal standards
- **Interactive Applications**: 
  - ✅ `htop` - System monitoring with full interactivity
  - ✅ `vim` - Full-featured text editor with all modes
  - ✅ `nano` - Text editor with complete functionality
  - ✅ `less` - File pager with navigation
  - ✅ `tmux` - Terminal multiplexer support
  - ✅ All ncurses-based applications work perfectly
- **Color Support**: Full 256-color palette support
- **Unicode Support**: Proper rendering of international characters
- **Cursor Styles**: Block, underline, or bar cursor options

#### 🔍 Command History Search (NEW!)
- **Fuzzy Search**: Find commands with partial matches - inspired by Warp terminal
- **Cross-Group Search**: Search command history across ALL terminal groups
- **Smart Ranking**: Results sorted by relevance and recency
- **Rich Context**: See when, where, and in which group commands were run
- **Persistent History**: Commands saved across sessions (up to 10,000 commands)
- **Quick Access**: Press `Ctrl+R` to instantly search your command history
- **Execute or Insert**: Choose to insert the command for review or execute immediately

### Command Buttons

#### 🎯 Custom Buttons
- **One-Click Execution**: Run complex commands with a single click
- **Custom Names**: Give buttons meaningful, descriptive names
- **Command Storage**: Save frequently used commands for quick access
- **Edit & Delete**: Modify or remove custom buttons at any time
- **Per-Group Storage**: Each group has its own set of command buttons

#### 📝 Default Commands
Pre-configured buttons for common operations:
- **Clear**: Clear the terminal screen
- **List Files**: Display directory contents (`ls -la`)
- **Show Path**: Display current working directory
- **Disk Usage**: Show available disk space
- **System Info**: Display system information

### Command Queue

#### 📋 FIFO Queue System
- **First-In-First-Out**: Commands execute in the order they're added
- **Batch Processing**: Queue multiple commands for sequential execution
- **Visual Feedback**: See queued commands and their status in real-time
- **Queue Controls**:
  - **Start**: Begin processing queued commands
  - **Stop**: Pause queue processing
  - **Kill**: Clear all queued commands
- **Safety Features**: Prevent command conflicts and race conditions

### 🎬 Session Recording & Playback

#### Record & Replay Command Sequences
- **✨ NEW: Direct Terminal Input**: Commands typed in terminal are now captured automatically!
- **Record Sessions**: Capture command sequences as you execute them
- **Multiple Recording Methods**:
  - Type commands directly in terminal (press Enter to capture)
  - Click command buttons to execute and record
  - Use Command Book to find and execute commands
  - Mix all methods - everything is captured together!
- **Automatic Playback**: Replay recorded sequences with one click
- **Playback Controls**: 
  - **Play**: Start executing the sequence (1 second delay between commands)
  - **Pause**: Temporarily halt execution
  - **Stop**: Cancel playback immediately
- **Edit Recordings**: 
  - Review and edit commands before saving
  - Fix typos or adjust commands
  - Modify existing recordings anytime
- **Usage Tracking**: See how many times each recording has been played
- **Import/Export**: Share recordings as JSON files with your team
- **Duplicate**: Create variations of existing recordings
- **Library Management**: Organize and manage all your recorded sequences
- **Perfect For**:
  - Development environment setup
  - Deployment workflows
  - Testing sequences
  - Database operations
  - Batch processing tasks
  - System administration
  - Training and onboarding

> 📖 **Learn More**: See [Session Recorder Guide](SESSION_RECORDER_GUIDE.md) for detailed documentation
> 
> 🎉 **What's New**: Commands typed directly in terminal are now captured! See [Update Notes](WHATS_NEW_RECORDER_UPDATE.md)

### File Attachments

#### 📎 File Management
- **Easy Attachment**: Add PEM keys, configuration files, scripts, and more
- **Environment Variables**: Attached files automatically become environment variables
- **Per-Group Storage**: Each group maintains its own file attachments
- **Quick Access**: Reference files in commands using environment variables
- **Common Use Cases**:
  - SSH private keys (`.pem`, `.key`)
  - Configuration files (`.conf`, `.json`, `.yaml`)
  - Scripts (`.sh`, `.py`, `.js`)
  - Certificates and credentials

### Modern UI

#### 🎨 User Interface
- **Dark Theme**: Professional dark theme easy on the eyes
- **Resizable Panels**: Adjust panel sizes to match your workflow
- **Toggle Panels**: Show/hide groups and buttons panels with toolbar buttons
- **Persistent Layout**: Window size and panel positions saved between sessions
- **Responsive Design**: Adapts to different screen sizes and resolutions
- **Visual Feedback**: Clear indicators for active elements and states

---

## 🚀 Installation

### Prerequisites

Before installing Terminal Browser, ensure you have:

- **Python 3.7 or higher**: Check with `python --version` or `python3 --version`
- **pip**: Python package installer (usually comes with Python)
- **Operating System**: macOS, Linux, or Windows

### Quick Setup

1. **Clone or Download the Repository**
```bash
cd terminal_browser
```

2. **Install Dependencies**
```bash
pip install -r requirements.txt
```

Or install manually:
```bash
   pip install PyQt5 pyte
   ```

3. **Run the Application**
   ```bash
   python main.py
   ```

### Building macOS App

To create a standalone macOS application:

1. **Install py2app**
   ```bash
   pip install py2app
   ```

2. **Build the App**
   ```bash
   python setup.py py2app
   ```

3. **Find Your App**
   ```bash
   open dist/
   ```
   
   The `Terminal Browser.app` will be in the `dist/` directory.

---

## 📖 Getting Started

### Launching the Application

**Command Line:**
```bash
python main.py
```

**Make Executable (Unix/Linux):**
```bash
chmod +x main.py
./main.py
```

**macOS App (after building):**
Double-click the `Terminal Browser.app` in the `dist/` folder.

### Creating Terminal Groups

Groups help you organize terminals by project, environment, or workflow:

1. Click the **"+ Add Group"** button in the left panel
2. Enter a descriptive name (e.g., "Frontend", "AWS Production", "Database")
3. The group appears in the sidebar
4. Click the group to activate it

**Group Management:**
- **Rename**: Right-click → Rename
- **Delete**: Right-click → Delete
- **Switch**: Simply click any group name

### Managing Terminal Tabs

Each group can have multiple terminal tabs:

1. **Create Tab**: Click the **"+"** button in the tab bar
2. **Select Shell**: Choose your preferred shell (bash, zsh, fish, etc.)
3. **Name Tab**: Give it a descriptive name
4. **Close Tab**: Click the **"×"** on the tab
5. **Rename Tab**: Right-click on tab → Rename
6. **Reorder Tabs**: Drag tabs to rearrange them

**Navigation:**
- **Scroll Tabs**: Use **◀** and **▶** buttons when tabs overflow
- **Quick Jump**: Right-click navigation buttons to see hidden tabs menu
- **Keyboard**: Use shortcuts to create and close tabs (see [Shortcuts](#-keyboard-shortcuts))

### Creating Command Buttons

Save frequently used commands as buttons:

1. Click **"+ Add Button"** in the right panel
2. Fill in the form:
   - **Button Name**: Descriptive name (e.g., "Deploy to Production")
   - **Command**: The shell command to execute
   - **Description**: Optional notes about what the command does
3. Click **"Save"**

**Example Commands:**
```bash
# Development
npm start
python manage.py runserver
docker-compose up

# Git Operations
git status
git pull origin main
git log --oneline -20

# Server Management
ssh user@server.com
systemctl restart nginx
docker ps -a
```

---

## 📘 Usage Guide

### Terminal Groups

#### Creating Effective Groups

**Project-Based Groups:**
```
📁 Frontend
📁 Backend
📁 Database
📁 DevOps
```

**Environment-Based Groups:**
```
🌍 Development
🌍 Staging
🌍 Production
```

**Task-Based Groups:**
```
⚡ Monitoring
⚡ Deployment
⚡ Testing
⚡ Debugging
```

#### Best Practices

- **Use Descriptive Names**: "AWS Production" > "Group 1"
- **Keep Groups Focused**: One project or environment per group
- **Regular Cleanup**: Delete unused groups to stay organized
- **Logical Grouping**: Group related tasks together

### Command Execution

#### Direct Execution
Type commands directly into the terminal:
```bash
ls -la
cd /path/to/directory
python script.py
```

#### Button Execution
Click command buttons for instant execution of saved commands.

#### Queue Execution
Click multiple buttons rapidly to add them to the queue:
1. Click first button → Added to queue
2. Click second button → Added to queue
3. Click **"Start Queue"** → Executes in order
4. Use **"Stop"** to pause or **"Kill"** to clear

### File Management

#### Attaching Files

1. Click **"+ Add File"** in the right panel
2. Browse and select your file
3. The file appears in the Files list
4. File is now available as an environment variable

#### Using Attached Files

Files are converted to environment variables:

**Example:**
- File: `mykey.pem`
- Variable: `$MYKEY_PEM`

**Usage in Commands:**
```bash
# SSH with attached key
ssh -i $MYKEY_PEM user@server.com

# Use config file
program --config $CONFIG_JSON
```

**Variable Naming Rules:**
- Uppercase letters
- Dots become underscores: `config.yaml` → `$CONFIG_YAML`
- Spaces become underscores: `my file.txt` → `$MY_FILE_TXT`

### Preferences

Access preferences via:
- **Menu**: Edit → Preferences
- **Toolbar**: Click **⚙ Preferences** button
- **Keyboard**: `Cmd+,` (macOS) or `Ctrl+,` (Windows/Linux)

#### Available Settings

**Font Settings:**
- **Font Family**: Choose from monospace fonts
- **Font Size**: 8-24pt (default: 13pt)

**Color Settings:**
- **Foreground Color**: Text color
- **Background Color**: Terminal background
- **Preset Themes**: Default, Green on Black, Solarized Dark

**Cursor Settings:**
- **Cursor Style**: Block, Underline, Bar
- **Cursor Blink**: Enable/disable blinking

---

## ⌨️ Keyboard Shortcuts

> **📚 NEW: Comprehensive Keyboard Shortcuts Documentation**
>
> For complete keyboard shortcuts documentation including **ALL nano shortcuts**, terminal control sequences, and detailed explanations:
>
> - 📖 **[Complete Shortcuts Guide](COMPLETE_SHORTCUTS_GUIDE.md)** - Full documentation with all shortcuts
> - 🎯 **[Quick Reference Card](SHORTCUTS_QUICK_REFERENCE.md)** - One-page printable reference
> - ✅ **[Test Guide](TEST_SHORTCUTS.md)** - Verify all shortcuts work correctly
>
> **✨ What's New:**
> - ✅ **ALL terminal shortcuts now work** - No exceptions!
> - ✅ **Full nano support** - Ctrl+X (exit), Ctrl+O (save), Ctrl+K (cut), etc.
> - ✅ **All vim shortcuts work** - Complete vim compatibility
> - ✅ **Tab completion** - Stays in terminal, doesn't move focus
> - ✅ **When terminal is in focus, it works exactly like a regular terminal!**

### File Operations

| Action | macOS | Windows/Linux |
|--------|-------|---------------|
| New Tab | `Cmd+T` or `Cmd+N` | `Ctrl+T` or `Ctrl+N` |
| Close Tab | `Cmd+W` | `Ctrl+Shift+W` |
| Quit Application | `Cmd+Q` | `Ctrl+Q` |

### Editing & Clipboard

| Action | macOS | Windows/Linux |
|--------|-------|---------------|
| Copy | `Cmd+C` | `Ctrl+Shift+C` |
| Paste | `Cmd+V` | `Ctrl+Shift+V` |
| Select All | `Cmd+A` | `Ctrl+Shift+A` |
| Cut | `Cmd+X` | `Ctrl+X` |

**Alternative Clipboard Shortcuts (All Platforms):**
- `Ctrl+Shift+C` - Copy
- `Ctrl+Shift+V` - Paste
- `Ctrl+Shift+A` - Select All

**Command History:**
- `Ctrl+R` - **Command History Search** (NEW!) - Fuzzy search across all command history

### View & Zoom

| Action | Shortcut |
|--------|----------|
| Zoom In | `Cmd/Ctrl + Plus` |
| Zoom Out | `Cmd/Ctrl + Minus` |
| Reset Zoom | `Ctrl + 0` |
| Preferences | `Cmd/Ctrl + Comma` |
| Help | `F1` |

### Terminal Control

> **✅ ALL terminal shortcuts work in nano, vim, and all interactive applications!**
> See the [Complete Shortcuts Guide](COMPLETE_SHORTCUTS_GUIDE.md) for full details.

**Command History:**
- `Up Arrow` - Previous command
- `Down Arrow` - Next command
- `Ctrl+R` - Reverse search history

**Cursor Navigation:**
- `Left/Right Arrow` - Move cursor
- `Home` - Beginning of line
- `End` - End of line
- `Ctrl+A` - Beginning of line (all platforms)
- `Ctrl+E` - End of line (all platforms)

**Control Sequences:**
- `Ctrl+C` - Interrupt/cancel running command
- `Ctrl+D` - Exit/EOF signal
- `Ctrl+L` - Clear screen
- `Ctrl+Z` - Suspend process
- `Tab` - Auto-complete (stays in terminal!)

**Line Editing (All Platforms):**
- `Ctrl+K` - Delete to end of line
- `Ctrl+U` - Delete to beginning of line
- `Ctrl+W` - Delete word before cursor
- `Ctrl+Y` - Paste (yank) killed text

**Nano Editor Shortcuts (All Work!):**
- `Ctrl+O` - Save file (Write Out)
- `Ctrl+X` - Exit nano
- `Ctrl+K` - Cut line
- `Ctrl+U` - Paste (Uncut)
- `Ctrl+W` - Search (Where Is)
- `Ctrl+\` - Replace
- `Ctrl+G` - Get Help
- See [Complete Shortcuts Guide](COMPLETE_SHORTCUTS_GUIDE.md) for all nano shortcuts

**Scrolling:**
- `Shift+PageUp` - Scroll up one page
- `Shift+PageDown` - Scroll down one page
- `Mouse Wheel` - Scroll through output
- `Two-finger scroll` - Trackpad scrolling (macOS)

---

## 🔥 Advanced Features

### Command Queue Management

#### Queue Workflow

```
Command Button Click → Added to Queue → Start Queue → FIFO Execution
```

#### Use Cases

**Deployment Pipeline:**
```
1. Run Tests
2. Build Application
3. Deploy to Staging
4. Run Smoke Tests
5. Deploy to Production
```

**Database Management:**
```
1. Backup Database
2. Run Migrations
3. Seed Data
4. Restart Services
```

### Environment Variables

#### Automatic Variables

All attached files become environment variables:

```bash
# Attached: database.conf
echo $DATABASE_CONF
# Output: /path/to/database.conf

# Attached: api-key.txt
cat $API_KEY_TXT
```

#### Using in Scripts

Create command buttons that use environment variables:

```bash
# Deploy with SSH key
./deploy.sh --key $DEPLOY_KEY_PEM --env production

# Run with config
python app.py --config $APP_CONFIG_JSON

# Backup with credentials
mysqldump --defaults-file=$DB_CREDENTIALS_CNF mydb > backup.sql
```

### State Persistence

#### Automatically Saved

- ✅ Window size and position
- ✅ Panel sizes and visibility
- ✅ All terminal groups
- ✅ Tabs per group (with shell types)
- ✅ Command buttons per group
- ✅ File attachments per group
- ✅ Current group selection

#### Settings Location

- **macOS**: `~/Library/Preferences/com.TerminalBrowser.plist`
- **Linux**: `~/.config/TerminalBrowser/`
- **Windows**: Registry (`HKEY_CURRENT_USER\Software\TerminalBrowser`)

#### Reset to Defaults

Delete the settings file/directory and restart the application.

---

## 💼 Use Cases

### DevOps & System Administration

**Server Management:**
- Monitor multiple servers simultaneously
- Quick SSH access with pre-configured keys
- Run deployment scripts with one click
- Manage Docker containers across environments

**Example Setup:**
```
Group: Production Servers
├── Tab: Web Server 1 (ssh user@web1)
├── Tab: Web Server 2 (ssh user@web2)
├── Tab: Database Server (ssh user@db)
└── Tab: Monitoring (htop)

Buttons:
- Deploy Application
- Restart Services
- Check Logs
- Backup Database
```

### Software Development

**Full-Stack Development:**
- Frontend and backend development in separate groups
- Quick access to build, test, and run commands
- Git operations with pre-configured buttons
- Database management in dedicated tabs

**Example Setup:**
```
Group: Frontend
├── Tab: Development Server (npm start)
├── Tab: Tests (npm test --watch)
└── Tab: Build (npm run build)

Group: Backend
├── Tab: API Server (python manage.py runserver)
├── Tab: Worker Queue (celery worker)
└── Tab: Database Shell (psql)
```

### Database Management

**Multi-Database Management:**
- Connect to multiple databases simultaneously
- Run common queries with button shortcuts
- Manage backups and migrations
- Monitor database performance

**Example Setup:**
```
Group: Databases
├── Tab: PostgreSQL Production
├── Tab: PostgreSQL Staging
├── Tab: MongoDB
└── Tab: Redis

Buttons:
- Show Active Connections
- Analyze Query Performance
- Backup Database
- Run Pending Migrations
```

### Cloud Infrastructure

**AWS/Azure/GCP Management:**
- Manage different cloud accounts in separate groups
- Quick access to CLI tools
- Infrastructure as Code deployments
- Resource monitoring and management

---

## 🔧 Troubleshooting

### Application Won't Start

**Check Python Version:**
```bash
python --version
# Should be 3.7 or higher
```

**Verify Dependencies:**
```bash
pip list | grep PyQt5
pip list | grep pyte
```

**Reinstall Dependencies:**
```bash
pip install -r requirements.txt --force-reinstall
```

### Commands Not Executing

- ✅ Ensure a terminal tab is selected
- ✅ Verify the command works in a regular terminal
- ✅ Check file permissions if running scripts
- ✅ Look for error messages in the terminal output

### Terminal Display Issues

**Text Not Visible:**
- Check Preferences → Colors
- Ensure foreground and background colors contrast
- Try preset themes (Green on Black, Solarized Dark)

**Font Too Small/Large:**
- Use Zoom shortcuts: `Cmd/Ctrl + Plus/Minus`
- Adjust in Preferences → Font Size
- Reset with `Ctrl + 0`

### Interactive Apps Not Working

If `htop`, `vim`, `nano`, etc. aren't working:

1. Verify `pyte` is installed: `pip install pyte`
2. Try in a regular terminal first
3. Resize the terminal window
4. Restart the terminal tab

### File Attachments Not Working

- Verify file exists at the specified path
- Check file permissions (should be readable)
- Use correct environment variable name (uppercase, underscores)
- Test with: `echo $VARIABLE_NAME`

### Performance Issues

**Slow Performance:**
- Close unused terminal tabs
- Delete old terminal groups
- Clear terminal output regularly
- Reduce font size

**High Memory Usage:**
- Terminal Browser caches sessions for quick switching
- Close groups not in active use
- Restart application periodically

### Settings Not Persisting

**Check Settings Location:**
```bash
# macOS
ls ~/Library/Preferences/com.TerminalBrowser.plist

# Linux
ls ~/.config/TerminalBrowser/

# Windows
reg query HKEY_CURRENT_USER\Software\TerminalBrowser
```

**Reset Settings:**
Delete the settings file/directory and restart.

---

## 📁 Project Structure

```
terminal_browser/
├── main.py                      # Application entry point
├── requirements.txt             # Python dependencies
├── setup.py                     # py2app build configuration
├── README.md                    # This file
│
├── ui/                          # User Interface components
│   ├── __init__.py
│   ├── main_window.py           # Main application window
│   ├── terminal_group_panel.py  # Left sidebar (groups)
│   ├── terminal_tabs.py         # Top tab bar
│   ├── pyte_terminal_widget.py  # Terminal emulation
│   ├── button_panel.py          # Right sidebar (buttons)
│   ├── preferences_dialog.py    # Preferences window
│   ├── help_dialog.py           # Help & documentation window
│   └── dialogs.py               # Various dialog windows
│
└── core/                        # Core functionality
    ├── __init__.py
    ├── command_queue.py         # Command queue management
    ├── state_manager.py         # Application state persistence
    └── preferences_manager.py   # User preferences management
```

---

## 🤝 Contributing

Contributions are welcome! Here are areas where you can help:

### Feature Requests
- Additional keyboard shortcuts
- More terminal features (split panes, etc.)
- Export/import configurations
- Additional themes and customization options
- Plugin system

### Bug Reports
Please include:
- Operating system and version
- Python version
- Steps to reproduce
- Expected vs. actual behavior
- Screenshots if applicable

### Pull Requests
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

---

## 📄 License

This project is open source and available under the **MIT License**.

```
MIT License

Copyright (c) 2025 Terminal Browser

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## 📞 Support

### Documentation
- **In-App Help**: Click **Help** button in toolbar or press `F1`
- **README**: This comprehensive guide
- **GitHub Wiki**: Coming soon

### Community
- **Issues**: [GitHub Issues](https://github.com/yourusername/terminal_browser/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/terminal_browser/discussions)

### Contact
For questions, suggestions, or feedback:
- Open an issue on GitHub
- Check the in-app documentation (❓ Help button)

---

## 🌟 Acknowledgments

- **PyQt5**: Powerful Python bindings for Qt
- **pyte**: Terminal emulator in Python for full VT100/ANSI support
- **Inspiration**: VSCode terminal, iTerm2, and modern browser tabs
- **Community**: Thanks to all contributors and users!

---

<div align="center">

**Happy Terminal Browsing!** 🚀

Made with ❤️ for developers, sysadmins, and DevOps professionals

[⬆ Back to Top](#terminal-browser-)

</div>
