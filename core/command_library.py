"""Command library with built-in and custom commands organized in folders"""

import json
import os
from datetime import datetime

class CommandLibrary:
    """Manages built-in and custom command library with folder structure"""
    
    def __init__(self):
        self.library_file = os.path.expanduser("~/.terminal_browser_commands.json")
        self.usage_stats = {}  # Track command usage: {command_id: count}
        self.custom_commands = {}  # Custom commands organized by folders
        self.load_library()
        
    def get_builtin_commands(self):
        """Get built-in command library organized in folders"""
        return {
            "Git": {
                "Basic": [
                    {"name": "Git Status", "command": "git status", "description": "Show working tree status"},
                    {"name": "Git Log", "command": "git log --oneline --graph --decorate --all", "description": "Show commit history"},
                    {"name": "Git Diff", "command": "git diff", "description": "Show changes in working directory"},
                    {"name": "Git Branch List", "command": "git branch -a", "description": "List all branches"},
                    {"name": "Git Remote", "command": "git remote -v", "description": "Show remote repositories"},
                ],
                "Committing": [
                    {"name": "Git Add All", "command": "git add .", "description": "Stage all changes"},
                    {"name": "Git Add File", "command": "git add [filename]", "description": "Stage specific file"},
                    {"name": "Git Commit", "command": "git commit -m '[message]'", "description": "Commit staged changes"},
                    {"name": "Git Commit All", "command": "git commit -am '[message]'", "description": "Stage and commit all changes"},
                    {"name": "Git Amend", "command": "git commit --amend --no-edit", "description": "Amend last commit"},
                ],
                "Branching": [
                    {"name": "Create Branch", "command": "git checkout -b [branch-name]", "description": "Create and switch to new branch"},
                    {"name": "Switch Branch", "command": "git checkout [branch-name]", "description": "Switch to existing branch"},
                    {"name": "Delete Branch", "command": "git branch -d [branch-name]", "description": "Delete local branch"},
                    {"name": "Merge Branch", "command": "git merge [branch-name]", "description": "Merge branch into current"},
                    {"name": "Rebase", "command": "git rebase [branch-name]", "description": "Rebase current branch"},
                ],
                "Remote": [
                    {"name": "Git Pull", "command": "git pull origin [branch-name]", "description": "Pull from remote"},
                    {"name": "Git Push", "command": "git push origin [branch-name]", "description": "Push to remote"},
                    {"name": "Git Fetch", "command": "git fetch --all", "description": "Fetch all remotes"},
                    {"name": "Force Push", "command": "git push --force-with-lease origin [branch-name]", "description": "Force push with safety"},
                    {"name": "Clone Repo", "command": "git clone [repo-url]", "description": "Clone repository"},
                ],
                "Stash": [
                    {"name": "Stash Changes", "command": "git stash", "description": "Stash working directory"},
                    {"name": "Stash Pop", "command": "git stash pop", "description": "Apply and remove stash"},
                    {"name": "Stash List", "command": "git stash list", "description": "List all stashes"},
                    {"name": "Stash Apply", "command": "git stash apply stash@{[index]}", "description": "Apply specific stash"},
                ],
                "Undo": [
                    {"name": "Unstage File", "command": "git reset HEAD [filename]", "description": "Unstage file"},
                    {"name": "Discard Changes", "command": "git checkout -- [filename]", "description": "Discard file changes"},
                    {"name": "Reset Soft", "command": "git reset --soft HEAD~1", "description": "Undo last commit, keep changes"},
                    {"name": "Reset Hard", "command": "git reset --hard HEAD~1", "description": "Undo last commit, discard changes"},
                ],
            },
            "File Operations": {
                "Navigation": [
                    {"name": "List Files", "command": "ls -lah", "description": "List all files with details"},
                    {"name": "List Tree", "command": "tree -L 2", "description": "Show directory tree"},
                    {"name": "Current Dir", "command": "pwd", "description": "Print working directory"},
                    {"name": "Go Home", "command": "cd ~", "description": "Go to home directory"},
                    {"name": "Go Up", "command": "cd ..", "description": "Go up one directory"},
                ],
                "Create": [
                    {"name": "Create File", "command": "touch [filename]", "description": "Create new file"},
                    {"name": "Create Directory", "command": "mkdir [dirname]", "description": "Create directory"},
                    {"name": "Create Nested Dir", "command": "mkdir -p [path/to/dir]", "description": "Create nested directories"},
                ],
                "Copy & Move": [
                    {"name": "Copy File", "command": "cp [source] [destination]", "description": "Copy file"},
                    {"name": "Copy Directory", "command": "cp -r [source] [destination]", "description": "Copy directory recursively"},
                    {"name": "Move/Rename", "command": "mv [source] [destination]", "description": "Move or rename file"},
                ],
                "Delete": [
                    {"name": "Remove File", "command": "rm [filename]", "description": "Remove file"},
                    {"name": "Remove Directory", "command": "rm -rf [dirname]", "description": "Remove directory recursively"},
                    {"name": "Remove Empty Dir", "command": "rmdir [dirname]", "description": "Remove empty directory"},
                ],
                "View & Edit": [
                    {"name": "View File", "command": "cat [filename]", "description": "Display file contents"},
                    {"name": "View with Less", "command": "less [filename]", "description": "View file with pagination"},
                    {"name": "View with Tail", "command": "tail -f [filename]", "description": "Follow file updates"},
                    {"name": "Edit with Vi", "command": "vi [filename]", "description": "Edit file with vi"},
                    {"name": "Edit with Nano", "command": "nano [filename]", "description": "Edit file with nano"},
                ],
                "Search": [
                    {"name": "Find File", "command": "find . -name '[filename]'", "description": "Find file by name"},
                    {"name": "Find in Files", "command": "grep -r '[pattern]' .", "description": "Search pattern in files"},
                    {"name": "Find Large Files", "command": "find . -type f -size +100M", "description": "Find files larger than 100MB"},
                ],
                "Permissions": [
                    {"name": "Change Permissions", "command": "chmod [mode] [filename]", "description": "Change file permissions"},
                    {"name": "Change Owner", "command": "chown [user]:[group] [filename]", "description": "Change file owner"},
                    {"name": "Make Executable", "command": "chmod +x [filename]", "description": "Make file executable"},
                ],
            },
            "DevOps": {
                "Docker": [
                    {"name": "Docker PS", "command": "docker ps -a", "description": "List all containers"},
                    {"name": "Docker Images", "command": "docker images", "description": "List all images"},
                    {"name": "Docker Build", "command": "docker build -t [image-name] .", "description": "Build Docker image"},
                    {"name": "Docker Run", "command": "docker run -d --name [container-name] [image-name]", "description": "Run container"},
                    {"name": "Docker Stop", "command": "docker stop [container-name]", "description": "Stop container"},
                    {"name": "Docker Logs", "command": "docker logs -f [container-name]", "description": "Follow container logs"},
                    {"name": "Docker Exec", "command": "docker exec -it [container-name] /bin/bash", "description": "Execute bash in container"},
                    {"name": "Docker Compose Up", "command": "docker-compose up -d", "description": "Start services"},
                    {"name": "Docker Compose Down", "command": "docker-compose down", "description": "Stop services"},
                    {"name": "Docker Prune", "command": "docker system prune -a", "description": "Clean up Docker system"},
                ],
                "Kubernetes": [
                    {"name": "K8s Get Pods", "command": "kubectl get pods", "description": "List pods"},
                    {"name": "K8s Get Services", "command": "kubectl get services", "description": "List services"},
                    {"name": "K8s Describe Pod", "command": "kubectl describe pod [pod-name]", "description": "Describe pod"},
                    {"name": "K8s Logs", "command": "kubectl logs -f [pod-name]", "description": "Follow pod logs"},
                    {"name": "K8s Exec", "command": "kubectl exec -it [pod-name] -- /bin/bash", "description": "Execute bash in pod"},
                    {"name": "K8s Apply", "command": "kubectl apply -f [filename]", "description": "Apply configuration"},
                    {"name": "K8s Delete", "command": "kubectl delete -f [filename]", "description": "Delete resources"},
                    {"name": "K8s Port Forward", "command": "kubectl port-forward [pod-name] [local-port]:[pod-port]", "description": "Forward port"},
                ],
                "AWS": [
                    {"name": "List S3 Buckets", "command": "aws s3 ls", "description": "List S3 buckets"},
                    {"name": "List EC2 Instances", "command": "aws ec2 describe-instances", "description": "List EC2 instances"},
                    {"name": "S3 Upload", "command": "aws s3 cp [filename] s3://[bucket-name]/", "description": "Upload to S3"},
                    {"name": "S3 Download", "command": "aws s3 cp s3://[bucket-name]/[filename] .", "description": "Download from S3"},
                    {"name": "S3 Sync", "command": "aws s3 sync [local-dir] s3://[bucket-name]/[path]", "description": "Sync directory to S3"},
                ],
                "SSH": [
                    {"name": "SSH Connect", "command": "ssh [user]@[host]", "description": "Connect via SSH"},
                    {"name": "SSH with Key", "command": "ssh -i [key-file] [user]@[host]", "description": "Connect with key file"},
                    {"name": "SCP Upload", "command": "scp [filename] [user]@[host]:[path]", "description": "Copy file to remote"},
                    {"name": "SCP Download", "command": "scp [user]@[host]:[path] [local-path]", "description": "Copy file from remote"},
                    {"name": "SSH Tunnel", "command": "ssh -L [local-port]:localhost:[remote-port] [user]@[host]", "description": "Create SSH tunnel"},
                ],
            },
            "Development": {
                "Python": [
                    {"name": "Python Run", "command": "python [filename]", "description": "Run Python script"},
                    {"name": "Pip Install", "command": "pip install [package]", "description": "Install Python package"},
                    {"name": "Pip List", "command": "pip list", "description": "List installed packages"},
                    {"name": "Create Venv", "command": "python -m venv venv", "description": "Create virtual environment"},
                    {"name": "Activate Venv", "command": "source venv/bin/activate", "description": "Activate virtual environment"},
                    {"name": "Requirements Freeze", "command": "pip freeze > requirements.txt", "description": "Save dependencies"},
                    {"name": "Requirements Install", "command": "pip install -r requirements.txt", "description": "Install from requirements"},
                    {"name": "Python Server", "command": "python -m http.server 8000", "description": "Start HTTP server"},
                ],
                "Node.js": [
                    {"name": "NPM Install", "command": "npm install", "description": "Install dependencies"},
                    {"name": "NPM Install Package", "command": "npm install [package]", "description": "Install package"},
                    {"name": "NPM Run Dev", "command": "npm run dev", "description": "Run dev server"},
                    {"name": "NPM Run Build", "command": "npm run build", "description": "Build project"},
                    {"name": "NPM Test", "command": "npm test", "description": "Run tests"},
                    {"name": "NPM Start", "command": "npm start", "description": "Start application"},
                    {"name": "NPM Init", "command": "npm init -y", "description": "Initialize package.json"},
                ],
                "Testing": [
                    {"name": "Pytest", "command": "pytest [test-file]", "description": "Run Python tests"},
                    {"name": "Jest", "command": "jest [test-file]", "description": "Run JavaScript tests"},
                    {"name": "Coverage", "command": "pytest --cov=[module]", "description": "Run with coverage"},
                ],
            },
            "System": {
                "Process": [
                    {"name": "Process List", "command": "ps aux", "description": "List all processes"},
                    {"name": "Top", "command": "top", "description": "Show system processes"},
                    {"name": "Htop", "command": "htop", "description": "Interactive process viewer"},
                    {"name": "Kill Process", "command": "kill [pid]", "description": "Kill process by PID"},
                    {"name": "Kill by Name", "command": "pkill [process-name]", "description": "Kill process by name"},
                ],
                "Network": [
                    {"name": "Check Port", "command": "lsof -i :[port]", "description": "Check what's using port"},
                    {"name": "Ping", "command": "ping [host]", "description": "Test connectivity"},
                    {"name": "Curl", "command": "curl [url]", "description": "Make HTTP request"},
                    {"name": "Wget", "command": "wget [url]", "description": "Download file"},
                    {"name": "Netstat", "command": "netstat -tuln", "description": "Show network connections"},
                ],
                "Disk": [
                    {"name": "Disk Usage", "command": "df -h", "description": "Show disk usage"},
                    {"name": "Directory Size", "command": "du -sh [dirname]", "description": "Show directory size"},
                    {"name": "Largest Dirs", "command": "du -h --max-depth=1 | sort -hr | head -10", "description": "Find largest directories"},
                ],
                "System Info": [
                    {"name": "System Info", "command": "uname -a", "description": "Show system information"},
                    {"name": "OS Release", "command": "cat /etc/os-release", "description": "Show OS release info"},
                    {"name": "CPU Info", "command": "lscpu", "description": "Show CPU information"},
                    {"name": "Memory Info", "command": "free -h", "description": "Show memory usage"},
                    {"name": "Uptime", "command": "uptime", "description": "Show system uptime"},
                ],
            },
            "Utilities": {
                "Compression": [
                    {"name": "Tar Create", "command": "tar -czf [archive.tar.gz] [directory]", "description": "Create tar.gz archive"},
                    {"name": "Tar Extract", "command": "tar -xzf [archive.tar.gz]", "description": "Extract tar.gz archive"},
                    {"name": "Zip Create", "command": "zip -r [archive.zip] [directory]", "description": "Create zip archive"},
                    {"name": "Unzip", "command": "unzip [archive.zip]", "description": "Extract zip archive"},
                    {"name": "Tar List", "command": "tar -tzf [archive.tar.gz]", "description": "List contents of tar.gz"},
                    {"name": "7z Compress", "command": "7z a [archive.7z] [directory]", "description": "Create 7z archive"},
                    {"name": "7z Extract", "command": "7z x [archive.7z]", "description": "Extract 7z archive"},
                ],
                "Text Processing": [
                    {"name": "Word Count", "command": "wc -l [filename]", "description": "Count lines in file"},
                    {"name": "Sort", "command": "sort [filename]", "description": "Sort file contents"},
                    {"name": "Unique", "command": "sort [filename] | uniq", "description": "Get unique lines"},
                    {"name": "Diff Files", "command": "diff [file1] [file2]", "description": "Compare two files"},
                    {"name": "Sed Replace", "command": "sed -i 's/[old]/[new]/g' [filename]", "description": "Replace text in file"},
                    {"name": "Awk Column", "command": "awk '{print $[column]}' [filename]", "description": "Extract specific column"},
                    {"name": "Head Lines", "command": "head -n [num] [filename]", "description": "Show first N lines"},
                    {"name": "Tail Lines", "command": "tail -n [num] [filename]", "description": "Show last N lines"},
                    {"name": "Cut Column", "command": "cut -d'[delimiter]' -f[field] [filename]", "description": "Extract column by delimiter"},
                    {"name": "Tr Replace", "command": "tr '[old]' '[new]' < [filename]", "description": "Translate characters"},
                ],
                "Miscellaneous": [
                    {"name": "Clear Screen", "command": "clear", "description": "Clear terminal screen"},
                    {"name": "History", "command": "history", "description": "Show command history"},
                    {"name": "Date", "command": "date", "description": "Show current date and time"},
                    {"name": "Calendar", "command": "cal", "description": "Show calendar"},
                    {"name": "Echo", "command": "echo '[text]'", "description": "Print text"},
                    {"name": "Env Vars", "command": "env", "description": "Show environment variables"},
                    {"name": "Which Command", "command": "which [command]", "description": "Show command location"},
                    {"name": "Alias List", "command": "alias", "description": "List all aliases"},
                    {"name": "Export Var", "command": "export [VAR]=[value]", "description": "Set environment variable"},
                ],
            },
            "Database": {
                "MySQL": [
                    {"name": "MySQL Connect", "command": "mysql -u [user] -p -h [host]", "description": "Connect to MySQL server"},
                    {"name": "MySQL Show Databases", "command": "mysql -u [user] -p -e 'SHOW DATABASES;'", "description": "List all databases"},
                    {"name": "MySQL Dump", "command": "mysqldump -u [user] -p [database] > [backup.sql]", "description": "Backup database"},
                    {"name": "MySQL Restore", "command": "mysql -u [user] -p [database] < [backup.sql]", "description": "Restore database"},
                    {"name": "MySQL Create DB", "command": "mysql -u [user] -p -e 'CREATE DATABASE [database];'", "description": "Create new database"},
                    {"name": "MySQL Drop DB", "command": "mysql -u [user] -p -e 'DROP DATABASE [database];'", "description": "Delete database"},
                ],
                "PostgreSQL": [
                    {"name": "Psql Connect", "command": "psql -U [user] -h [host] -d [database]", "description": "Connect to PostgreSQL"},
                    {"name": "Psql List DBs", "command": "psql -U [user] -l", "description": "List all databases"},
                    {"name": "Pg Dump", "command": "pg_dump -U [user] [database] > [backup.sql]", "description": "Backup database"},
                    {"name": "Pg Restore", "command": "psql -U [user] [database] < [backup.sql]", "description": "Restore database"},
                    {"name": "Pg Create DB", "command": "createdb -U [user] [database]", "description": "Create new database"},
                    {"name": "Pg Drop DB", "command": "dropdb -U [user] [database]", "description": "Delete database"},
                ],
                "MongoDB": [
                    {"name": "Mongo Connect", "command": "mongo [host]:[port]/[database]", "description": "Connect to MongoDB"},
                    {"name": "Mongo Dump", "command": "mongodump --db [database] --out [backup-dir]", "description": "Backup database"},
                    {"name": "Mongo Restore", "command": "mongorestore --db [database] [backup-dir]/[database]", "description": "Restore database"},
                    {"name": "Mongo Export", "command": "mongoexport --db [database] --collection [collection] --out [file.json]", "description": "Export collection"},
                    {"name": "Mongo Import", "command": "mongoimport --db [database] --collection [collection] --file [file.json]", "description": "Import collection"},
                ],
                "Redis": [
                    {"name": "Redis CLI", "command": "redis-cli", "description": "Open Redis CLI"},
                    {"name": "Redis Ping", "command": "redis-cli ping", "description": "Test Redis connection"},
                    {"name": "Redis Get Keys", "command": "redis-cli KEYS '*'", "description": "List all keys"},
                    {"name": "Redis Flush All", "command": "redis-cli FLUSHALL", "description": "Clear all data"},
                    {"name": "Redis Save", "command": "redis-cli SAVE", "description": "Save database to disk"},
                ],
            },
            "Web Development": {
                "Frontend": [
                    {"name": "React Create App", "command": "npx create-react-app [app-name]", "description": "Create new React app"},
                    {"name": "Vue Create", "command": "npm init vue@latest", "description": "Create new Vue app"},
                    {"name": "Angular New", "command": "ng new [app-name]", "description": "Create new Angular app"},
                    {"name": "Next.js Create", "command": "npx create-next-app@latest [app-name]", "description": "Create Next.js app"},
                    {"name": "Vite Create", "command": "npm create vite@latest [app-name]", "description": "Create Vite project"},
                    {"name": "Tailwind Init", "command": "npx tailwindcss init", "description": "Initialize Tailwind CSS"},
                ],
                "Backend": [
                    {"name": "Express Generator", "command": "npx express-generator [app-name]", "description": "Create Express app"},
                    {"name": "Django Create", "command": "django-admin startproject [project-name]", "description": "Create Django project"},
                    {"name": "Flask Run", "command": "flask run", "description": "Run Flask development server"},
                    {"name": "FastAPI Run", "command": "uvicorn main:app --reload", "description": "Run FastAPI with reload"},
                    {"name": "Rails New", "command": "rails new [app-name]", "description": "Create Ruby on Rails app"},
                    {"name": "Laravel New", "command": "laravel new [app-name]", "description": "Create Laravel project"},
                ],
                "API Testing": [
                    {"name": "Curl GET", "command": "curl -X GET [url]", "description": "HTTP GET request"},
                    {"name": "Curl POST", "command": "curl -X POST -H 'Content-Type: application/json' -d '{[data]}' [url]", "description": "HTTP POST with JSON"},
                    {"name": "Curl PUT", "command": "curl -X PUT -H 'Content-Type: application/json' -d '{[data]}' [url]", "description": "HTTP PUT with JSON"},
                    {"name": "Curl DELETE", "command": "curl -X DELETE [url]", "description": "HTTP DELETE request"},
                    {"name": "Curl Auth", "command": "curl -u [user]:[pass] [url]", "description": "Request with basic auth"},
                    {"name": "HTTPie GET", "command": "http GET [url]", "description": "HTTPie GET request"},
                    {"name": "HTTPie POST", "command": "http POST [url] [key]=[value]", "description": "HTTPie POST request"},
                ],
            },
            "Security": {
                "SSL/TLS": [
                    {"name": "Check SSL Cert", "command": "openssl s_client -connect [host]:[port] -showcerts", "description": "View SSL certificate"},
                    {"name": "Generate SSL Key", "command": "openssl genrsa -out [key.pem] 2048", "description": "Generate RSA private key"},
                    {"name": "Generate CSR", "command": "openssl req -new -key [key.pem] -out [csr.pem]", "description": "Generate certificate signing request"},
                    {"name": "Self-Signed Cert", "command": "openssl req -x509 -newkey rsa:2048 -keyout [key.pem] -out [cert.pem] -days 365 -nodes", "description": "Create self-signed certificate"},
                    {"name": "View Certificate", "command": "openssl x509 -in [cert.pem] -text -noout", "description": "Display certificate details"},
                ],
                "Hashing": [
                    {"name": "MD5 Hash", "command": "md5sum [filename]", "description": "Calculate MD5 checksum"},
                    {"name": "SHA256 Hash", "command": "sha256sum [filename]", "description": "Calculate SHA256 checksum"},
                    {"name": "SHA1 Hash", "command": "sha1sum [filename]", "description": "Calculate SHA1 checksum"},
                    {"name": "Base64 Encode", "command": "base64 [filename]", "description": "Encode file to base64"},
                    {"name": "Base64 Decode", "command": "base64 -d [filename]", "description": "Decode base64 file"},
                ],
                "Permissions": [
                    {"name": "Check Permissions", "command": "ls -la [filename]", "description": "View file permissions"},
                    {"name": "Set 755", "command": "chmod 755 [filename]", "description": "Set rwxr-xr-x permissions"},
                    {"name": "Set 644", "command": "chmod 644 [filename]", "description": "Set rw-r--r-- permissions"},
                    {"name": "Recursive Chmod", "command": "chmod -R [mode] [directory]", "description": "Change permissions recursively"},
                    {"name": "Change Group", "command": "chgrp [group] [filename]", "description": "Change file group"},
                ],
                "Network Security": [
                    {"name": "Scan Ports", "command": "nmap -p- [host]", "description": "Scan all ports"},
                    {"name": "Nmap Quick", "command": "nmap -T4 -A -v [host]", "description": "Quick comprehensive scan"},
                    {"name": "Check Firewall", "command": "sudo iptables -L -n -v", "description": "List firewall rules"},
                    {"name": "Tcpdump", "command": "sudo tcpdump -i [interface] -n", "description": "Capture network packets"},
                ],
            },
            "Build Tools": {
                "Make": [
                    {"name": "Make", "command": "make", "description": "Build using Makefile"},
                    {"name": "Make Clean", "command": "make clean", "description": "Clean build artifacts"},
                    {"name": "Make Install", "command": "sudo make install", "description": "Install built software"},
                    {"name": "Make Target", "command": "make [target]", "description": "Build specific target"},
                ],
                "CMake": [
                    {"name": "CMake Generate", "command": "cmake -B build", "description": "Generate build files"},
                    {"name": "CMake Build", "command": "cmake --build build", "description": "Build project"},
                    {"name": "CMake Install", "command": "cmake --install build", "description": "Install project"},
                    {"name": "CMake Clean", "command": "cmake --build build --target clean", "description": "Clean build"},
                ],
                "Gradle": [
                    {"name": "Gradle Build", "command": "./gradlew build", "description": "Build with Gradle"},
                    {"name": "Gradle Clean", "command": "./gradlew clean", "description": "Clean build directory"},
                    {"name": "Gradle Test", "command": "./gradlew test", "description": "Run tests"},
                    {"name": "Gradle Run", "command": "./gradlew run", "description": "Run application"},
                ],
                "Maven": [
                    {"name": "Maven Clean", "command": "mvn clean", "description": "Clean build directory"},
                    {"name": "Maven Install", "command": "mvn install", "description": "Build and install"},
                    {"name": "Maven Test", "command": "mvn test", "description": "Run tests"},
                    {"name": "Maven Package", "command": "mvn package", "description": "Package application"},
                ],
            },
            "Version Control": {
                "SVN": [
                    {"name": "SVN Checkout", "command": "svn checkout [url] [dir]", "description": "Checkout repository"},
                    {"name": "SVN Update", "command": "svn update", "description": "Update working copy"},
                    {"name": "SVN Commit", "command": "svn commit -m '[message]'", "description": "Commit changes"},
                    {"name": "SVN Status", "command": "svn status", "description": "Show file status"},
                    {"name": "SVN Add", "command": "svn add [filename]", "description": "Add file to version control"},
                    {"name": "SVN Log", "command": "svn log", "description": "Show commit history"},
                ],
                "Mercurial": [
                    {"name": "Hg Clone", "command": "hg clone [url]", "description": "Clone repository"},
                    {"name": "Hg Pull", "command": "hg pull", "description": "Pull changes"},
                    {"name": "Hg Update", "command": "hg update", "description": "Update working directory"},
                    {"name": "Hg Commit", "command": "hg commit -m '[message]'", "description": "Commit changes"},
                    {"name": "Hg Push", "command": "hg push", "description": "Push changes"},
                    {"name": "Hg Status", "command": "hg status", "description": "Show file status"},
                ],
            },
            "Package Managers": {
                "Homebrew": [
                    {"name": "Brew Install", "command": "brew install [package]", "description": "Install package"},
                    {"name": "Brew Update", "command": "brew update", "description": "Update Homebrew"},
                    {"name": "Brew Upgrade", "command": "brew upgrade", "description": "Upgrade all packages"},
                    {"name": "Brew Search", "command": "brew search [query]", "description": "Search for packages"},
                    {"name": "Brew List", "command": "brew list", "description": "List installed packages"},
                    {"name": "Brew Uninstall", "command": "brew uninstall [package]", "description": "Remove package"},
                    {"name": "Brew Info", "command": "brew info [package]", "description": "Show package info"},
                ],
                "APT": [
                    {"name": "Apt Update", "command": "sudo apt update", "description": "Update package list"},
                    {"name": "Apt Upgrade", "command": "sudo apt upgrade", "description": "Upgrade packages"},
                    {"name": "Apt Install", "command": "sudo apt install [package]", "description": "Install package"},
                    {"name": "Apt Remove", "command": "sudo apt remove [package]", "description": "Remove package"},
                    {"name": "Apt Search", "command": "apt search [query]", "description": "Search for packages"},
                    {"name": "Apt Autoremove", "command": "sudo apt autoremove", "description": "Remove unused packages"},
                ],
                "YUM/DNF": [
                    {"name": "Yum Install", "command": "sudo yum install [package]", "description": "Install package"},
                    {"name": "Yum Update", "command": "sudo yum update", "description": "Update packages"},
                    {"name": "Yum Remove", "command": "sudo yum remove [package]", "description": "Remove package"},
                    {"name": "DNF Install", "command": "sudo dnf install [package]", "description": "Install package (DNF)"},
                    {"name": "DNF Search", "command": "dnf search [query]", "description": "Search for packages"},
                ],
                "Conda": [
                    {"name": "Conda Create Env", "command": "conda create -n [env-name] python=[version]", "description": "Create environment"},
                    {"name": "Conda Activate", "command": "conda activate [env-name]", "description": "Activate environment"},
                    {"name": "Conda Deactivate", "command": "conda deactivate", "description": "Deactivate environment"},
                    {"name": "Conda Install", "command": "conda install [package]", "description": "Install package"},
                    {"name": "Conda List", "command": "conda list", "description": "List installed packages"},
                    {"name": "Conda Env List", "command": "conda env list", "description": "List all environments"},
                    {"name": "Conda Remove Env", "command": "conda env remove -n [env-name]", "description": "Remove environment"},
                ],
            },
            "Monitoring": {
                "Logs": [
                    {"name": "Journalctl", "command": "journalctl -u [service] -f", "description": "Follow service logs"},
                    {"name": "Tail Syslog", "command": "tail -f /var/log/syslog", "description": "Follow system log"},
                    {"name": "Dmesg", "command": "dmesg | tail", "description": "Show kernel messages"},
                    {"name": "Last Login", "command": "last", "description": "Show login history"},
                ],
                "Performance": [
                    {"name": "Iostat", "command": "iostat -x 2", "description": "Monitor I/O statistics"},
                    {"name": "Vmstat", "command": "vmstat 2", "description": "Monitor virtual memory"},
                    {"name": "Sar", "command": "sar -u 2 10", "description": "System activity report"},
                    {"name": "Iotop", "command": "sudo iotop", "description": "Monitor I/O by process"},
                    {"name": "Nmon", "command": "nmon", "description": "Performance monitor"},
                ],
                "Services": [
                    {"name": "Systemctl Status", "command": "systemctl status [service]", "description": "Check service status"},
                    {"name": "Systemctl Start", "command": "sudo systemctl start [service]", "description": "Start service"},
                    {"name": "Systemctl Stop", "command": "sudo systemctl stop [service]", "description": "Stop service"},
                    {"name": "Systemctl Restart", "command": "sudo systemctl restart [service]", "description": "Restart service"},
                    {"name": "Systemctl Enable", "command": "sudo systemctl enable [service]", "description": "Enable service at boot"},
                    {"name": "Systemctl List", "command": "systemctl list-units --type=service", "description": "List all services"},
                ],
            },
        }
    
    def add_custom_command(self, folder_path, name, command, description=""):
        """Add a custom command to a folder (folder_path can be nested like 'Work/AWS')"""
        cmd_id = f"custom_{len(self.custom_commands)}_{datetime.now().timestamp()}"
        
        # Create nested folder structure
        current = self.custom_commands
        folders = folder_path.split('/')
        for folder in folders[:-1]:
            if folder not in current:
                current[folder] = {}
            current = current[folder]
        
        # Add command to final folder
        final_folder = folders[-1]
        if final_folder not in current:
            current[final_folder] = []
        
        current[final_folder].append({
            'id': cmd_id,
            'name': name,
            'command': command,
            'description': description
        })
        
        self.save_library()
        return cmd_id
    
    def delete_custom_command(self, cmd_id):
        """Delete a custom command by ID"""
        def delete_recursive(obj):
            if isinstance(obj, dict):
                for key, value in list(obj.items()):
                    if isinstance(value, list):
                        obj[key] = [cmd for cmd in value if cmd.get('id') != cmd_id]
                    else:
                        delete_recursive(value)
            
        delete_recursive(self.custom_commands)
        self.save_library()
    
    def update_custom_command(self, cmd_id, name=None, command=None, description=None):
        """Update a custom command"""
        def update_recursive(obj):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if isinstance(value, list):
                        for cmd in value:
                            if cmd.get('id') == cmd_id:
                                if name is not None:
                                    cmd['name'] = name
                                if command is not None:
                                    cmd['command'] = command
                                if description is not None:
                                    cmd['description'] = description
                                return True
                    elif update_recursive(value):
                        return True
            return False
        
        if update_recursive(self.custom_commands):
            self.save_library()
            return True
        return False
    
    def track_usage(self, command_id):
        """Track command usage"""
        if command_id not in self.usage_stats:
            self.usage_stats[command_id] = 0
        self.usage_stats[command_id] += 1
        self.save_library()
    
    def get_recently_used(self, limit=20):
        """Get recently used commands sorted by usage count"""
        # Get all commands (builtin and custom)
        all_commands = []
        
        # Add builtin commands
        builtin = self.get_builtin_commands()
        for category, subcats in builtin.items():
            for subcat, commands in subcats.items():
                for cmd in commands:
                    cmd_id = f"builtin_{category}_{subcat}_{cmd['name']}"
                    usage_count = self.usage_stats.get(cmd_id, 0)
                    if usage_count > 0:
                        all_commands.append({
                            'id': cmd_id,
                            'name': cmd['name'],
                            'command': cmd['command'],
                            'description': cmd['description'],
                            'usage_count': usage_count,
                            'type': 'builtin',
                            'path': f"{category} > {subcat}"
                        })
        
        # Add custom commands
        def collect_custom(obj, path=""):
            commands = []
            if isinstance(obj, dict):
                for key, value in obj.items():
                    new_path = f"{path} > {key}" if path else key
                    if isinstance(value, list):
                        for cmd in value:
                            usage_count = self.usage_stats.get(cmd['id'], 0)
                            if usage_count > 0:
                                commands.append({
                                    'id': cmd['id'],
                                    'name': cmd['name'],
                                    'command': cmd['command'],
                                    'description': cmd.get('description', ''),
                                    'usage_count': usage_count,
                                    'type': 'custom',
                                    'path': new_path
                                })
                    else:
                        commands.extend(collect_custom(value, new_path))
            return commands
        
        all_commands.extend(collect_custom(self.custom_commands))
        
        # Sort by usage count
        all_commands.sort(key=lambda x: x['usage_count'], reverse=True)
        return all_commands[:limit]
    
    def save_library(self):
        """Save custom commands and usage stats to file"""
        try:
            data = {
                'custom_commands': self.custom_commands,
                'usage_stats': self.usage_stats,
                'last_saved': datetime.now().isoformat()
            }
            with open(self.library_file, 'w') as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            return False
    
    def load_library(self):
        """Load custom commands and usage stats from file"""
        try:
            if os.path.exists(self.library_file):
                with open(self.library_file, 'r') as f:
                    data = json.load(f)
                    self.custom_commands = data.get('custom_commands', {})
                    self.usage_stats = data.get('usage_stats', {})
            return True
        except Exception as e:
            return False
    
    def get_custom_commands(self):
        """Get custom commands organized in folders"""
        return self.custom_commands
    
    def create_custom_folder(self, folder_path):
        """Create a new folder in custom commands"""
        current = self.custom_commands
        folders = folder_path.split('/')
        for folder in folders:
            if folder not in current:
                current[folder] = {}
            current = current[folder]
        self.save_library()
    
    def delete_custom_folder(self, folder_path):
        """Delete a folder from custom commands"""
        folders = folder_path.split('/')
        current = self.custom_commands
        
        # Navigate to parent
        for folder in folders[:-1]:
            if folder not in current:
                return False
            current = current[folder]
        
        # Delete final folder
        if folders[-1] in current:
            del current[folders[-1]]
            self.save_library()
            return True
        return False

