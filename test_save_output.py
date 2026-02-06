#!/usr/bin/env python3
"""
Test script to verify the save terminal output feature
This script prints colored text that can be used to test the save functionality
"""

# ANSI color codes
RESET = '\033[0m'
BOLD = '\033[1m'
UNDERLINE = '\033[4m'

# Foreground colors
BLACK = '\033[30m'
RED = '\033[31m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
BLUE = '\033[34m'
MAGENTA = '\033[35m'
CYAN = '\033[36m'
WHITE = '\033[37m'

# Bright foreground colors
BRIGHT_BLACK = '\033[90m'
BRIGHT_RED = '\033[91m'
BRIGHT_GREEN = '\033[92m'
BRIGHT_YELLOW = '\033[93m'
BRIGHT_BLUE = '\033[94m'
BRIGHT_MAGENTA = '\033[95m'
BRIGHT_CYAN = '\033[96m'
BRIGHT_WHITE = '\033[97m'

# Background colors
BG_RED = '\033[41m'
BG_GREEN = '\033[42m'
BG_BLUE = '\033[44m'

def print_test_output():
    """Print various colored text for testing"""
    print(f"{BOLD}=== Terminal Output Save Test ==={RESET}\n")
    
    print(f"{RED}Red text{RESET}")
    print(f"{GREEN}Green text{RESET}")
    print(f"{BLUE}Blue text{RESET}")
    print(f"{YELLOW}Yellow text{RESET}")
    print(f"{MAGENTA}Magenta text{RESET}")
    print(f"{CYAN}Cyan text{RESET}")
    print()
    
    print(f"{BOLD}Bold text{RESET}")
    print(f"{UNDERLINE}Underlined text{RESET}")
    print(f"{BOLD}{RED}Bold red text{RESET}")
    print()
    
    print(f"{BRIGHT_RED}Bright red text{RESET}")
    print(f"{BRIGHT_GREEN}Bright green text{RESET}")
    print(f"{BRIGHT_BLUE}Bright blue text{RESET}")
    print()
    
    print(f"{BG_RED}{WHITE}White text on red background{RESET}")
    print(f"{BG_GREEN}{BLACK}Black text on green background{RESET}")
    print(f"{BG_BLUE}{WHITE}White text on blue background{RESET}")
    print()
    
    print(f"{BOLD}{CYAN}=== Line Numbers Test ==={RESET}")
    for i in range(1, 11):
        print(f"Line {i}: This is a numbered test line with some content")
    print()
    
    print(f"{GREEN}✓ Test complete! Now use 'File > Save Terminal Output...' to save this.{RESET}")

if __name__ == "__main__":
    print_test_output()
