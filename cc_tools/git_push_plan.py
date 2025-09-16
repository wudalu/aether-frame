#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Git Two-Phase Commit Script for feat_e2e_test Branch
==================================================

This script commits all changes in two phases with execution chain logging improvements.

🚀 USAGE:
---------
# Interactive Mode (Recommended)
python git_push_plan.py

# Execute Phase 1 (Documentation and Logging Infrastructure)
python git_push_plan.py 1

# Execute Phase 2 (Execution Chain Implementation)
python git_push_plan.py 2

# Execute Both Phases
python git_push_plan.py all

# Copy files to external directory
python git_push_plan.py copy <target_directory>

📋 PHASES:
-----------
Phase 1: Documentation and Logging Infrastructure
- docs/framework_abstraction.md contract updates
- src/aether_frame/common/unified_logging.py execution chain logging
- README.md E2E test command addition

Phase 2: Execution Chain Implementation  
- src/aether_frame/framework/adk/adk_adapter.py logging integration
- src/aether_frame/agents/adk/adk_domain_agent.py execution chain tracking
- src/aether_frame/tools/service.py tool execution logging

⚡ FEATURES:
-----------
✅ Automatic code quality checks (lint + type-check)  
✅ Interactive confirmation before each commit
✅ Colored output for better readability
✅ File existence validation
✅ Safe rollback on failures
✅ Copy mode for external directory commits
✅ Cross-platform compatibility (Windows PowerShell/Linux/macOS)

"""

import sys
import subprocess
import os
import shutil
from typing import List
import argparse
from pathlib import Path


class GitTwoPhaseCommit:
    """Git two-phase commit execution manager"""
    
    def __init__(self):
        self.phases = {
            1: {
                "name": "Documentation and Logging Infrastructure",
                "description": "docs: update contract documentation and add execution chain logging infrastructure",
                "files": [
                    "docs/framework_abstraction.md",
                    "src/aether_frame/common/unified_logging.py", 
                    "README.md"
                ]
            },
            2: {
                "name": "Execution Chain Implementation",
                "description": "feat: implement execution chain logging across TaskRequest → AgentRequest → ToolRequest flow",
                "files": [
                    "src/aether_frame/framework/adk/adk_adapter.py",
                    "src/aether_frame/agents/adk/adk_domain_agent.py",
                    "src/aether_frame/tools/service.py"
                ]
            }
        }
    
    def print_colored(self, text: str, color: str = "white") -> None:
        """Print colored text to console (cross-platform compatible)"""
        colors = {
            "red": "\033[91m",
            "green": "\033[92m", 
            "yellow": "\033[93m",
            "blue": "\033[94m",
            "magenta": "\033[95m",
            "cyan": "\033[96m",
            "white": "\033[97m",
            "bold": "\033[1m",
            "reset": "\033[0m"
        }
        
        # For Windows compatibility, check if we can use colors
        if os.name == 'nt':
            try:
                # Try to enable ANSI color support on Windows
                import msvcrt
                color_code = colors.get(color, colors["white"])
                print(f"{color_code}{text}{colors['reset']}")
            except ImportError:
                # Fallback to simple text on Windows without color support
                print(f"[{color.upper()}] {text}")
        else:
            color_code = colors.get(color, colors["white"])
            print(f"{color_code}{text}{colors['reset']}")
    
    def run_command(self, cmd: List[str], capture_output: bool = False, cwd: str = None) -> tuple:
        """Run shell command and return (success, output)"""
        try:
            if capture_output:
                result = subprocess.run(cmd, capture_output=True, text=True, check=True, cwd=cwd)
                return True, result.stdout.strip()
            else:
                result = subprocess.run(cmd, check=True, cwd=cwd)
                return True, ""
        except subprocess.CalledProcessError as e:
            if capture_output:
                return False, e.stderr.strip() if e.stderr else str(e)
            else:
                return False, str(e)
    
    def run_checks(self) -> bool:
        """Run code quality checks"""
        self.print_colored("Running code quality checks...", "yellow")
        
        # Check if dev.py exists
        if not os.path.exists("dev.py"):
            self.print_colored("dev.py not found, skipping quality checks", "yellow")
            return True
        
        # Run linting
        self.print_colored("Running linter...", "cyan")
        success, output = self.run_command(["python", "dev.py", "lint"])
        if not success:
            self.print_colored("WARNING: Linting failed. You may want to fix issues before committing.", "yellow")
            if output:
                print(output)
            choice = input("Continue anyway? (y/n): ").strip().lower()
            if choice not in ['y', 'yes']:
                return False
        
        # Run type checking
        self.print_colored("Running type checker...", "cyan")  
        success, output = self.run_command(["python", "dev.py", "type-check"])
        if not success:
            self.print_colored("WARNING: Type checking failed. You may want to fix issues before committing.", "yellow")
            if output:
                print(output)
            choice = input("Continue anyway? (y/n): ").strip().lower()
            if choice not in ['y', 'yes']:
                return False
        
        self.print_colored("Code quality checks passed.", "green")
        return True
    
    def check_status(self) -> None:
        """Check and display git status"""
        print()
        self.print_colored("Current git status:", "cyan")
        self.run_command(["git", "status", "--short"])
        print()
        self.print_colored("Diff statistics:", "cyan")
        self.run_command(["git", "diff", "--stat"])
        print()
    
    def show_commit_preview(self) -> None:
        """Show files to be committed"""
        print()
        self.print_colored("Files to be committed:", "yellow")
        self.run_command(["git", "diff", "--cached", "--stat"])
        print()
    
    def add_files(self, files: List[str]) -> None:
        """Add files to git staging area"""
        for file_path in files:
            if os.path.exists(file_path):
                self.print_colored(f"Adding {file_path}...", "green")
                success, output = self.run_command(["git", "add", file_path])
                if not success:
                    self.print_colored(f"Warning: Failed to add {file_path}: {output}", "yellow")
            else:
                self.print_colored(f"Skipping {file_path} (not found)", "yellow")
    
    def copy_files(self, target_dir: str, files: List[str]) -> bool:
        """Copy files to target directory maintaining structure"""
        target_path = Path(target_dir)
        target_path.mkdir(parents=True, exist_ok=True)
        
        copied_count = 0
        for file_path in files:
            source_path = Path(file_path)
            
            if source_path.exists():
                target_file_path = target_path / file_path
                target_file_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_path, target_file_path)
                self.print_colored(f"Copied file {file_path}", "green")
                copied_count += 1
            else:
                self.print_colored(f"Skipping {file_path} (not found)", "yellow")
        
        self.print_colored(f"Copied {copied_count} items to {target_dir}", "cyan")
        return copied_count > 0
    
    def execute_copy_mode(self, target_dir: str) -> bool:
        """Execute copy mode for external directory"""
        self.print_colored("=== COPY MODE ===", "magenta")
        self.print_colored(f"Target directory: {target_dir}", "cyan")
        
        # Copy all files from both phases
        all_files = []
        for phase in self.phases.values():
            all_files.extend(phase["files"])
        
        return self.copy_files(target_dir, all_files)
    
    def execute_phase(self, phase_num: int) -> bool:
        """Execute a specific phase"""
        if phase_num not in self.phases:
            self.print_colored(f"Invalid phase number: {phase_num}", "red")
            return False
        
        phase = self.phases[phase_num]
        
        self.print_colored("=" * 60, "magenta")
        self.print_colored(f"Phase {phase_num}: {phase['name']}", "magenta")
        self.print_colored("=" * 60, "magenta")
        
        self.check_status()
        
        # Add files for this phase
        self.add_files(phase["files"])
        
        self.show_commit_preview()
        
        # Check line count before commit confirmation
        success, diff_output = self.run_command(["git", "diff", "--cached", "--stat"], capture_output=True)
        if success and diff_output:
            lines = diff_output.split()
            insertions = 0
            deletions = 0
            
            # Extract insertion/deletion counts from git diff --stat output
            for i, word in enumerate(lines):
                if "insertion" in word and i > 0:
                    try:
                        insertions = int(lines[i-1])
                    except (ValueError, IndexError):
                        pass
                elif "deletion" in word and i > 0:
                    try:
                        deletions = int(lines[i-1])
                    except (ValueError, IndexError):
                        pass
            
            total_lines = insertions + deletions
            if total_lines > 0:
                self.print_colored(f"Estimated lines in this commit: {total_lines} (~{insertions} insertions, ~{deletions} deletions)", "cyan")
        
        # Confirm commit
        confirm = input(f"Proceed with Phase {phase_num} commit? (y/n): ").strip().lower()
        if confirm not in ['y', 'yes']:
            self.print_colored(f"Phase {phase_num} cancelled.", "yellow")
            self.run_command(["git", "reset"])
            return False
        
        # Run quality checks
        if not self.run_checks():
            self.run_command(["git", "reset"])
            return False
        
        # Create detailed commit message
        if phase_num == 1:
            commit_message = f"""{phase['description']}

This commit includes:
- Contract alignment between docs/framework_abstraction.md and implementation
- Unified logging infrastructure with execution chain support  
- README.md update with E2E test command

Key changes:
- Updated TaskResult, AgentRequest, AgentResponse, ToolRequest, ToolResult definitions in documentation
- Added log_execution_chain() method to unified_logging.py
- Added E2E test command to README.md for execution chain verification

Phase {phase_num}/2 of execution chain logging implementation

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>"""
        else:  # phase_num == 2
            commit_message = f"""{phase['description']}

This commit includes:
- Complete execution chain logging: TaskRequest → AgentRequest → ToolRequest → ToolResponse → AgentResponse → TaskResult
- Integration with unified logging infrastructure
- Real-time execution flow tracking for debugging

Key improvements:
- ADK adapter execution chain logging in adk_adapter.py
- Agent domain execution tracking in adk_domain_agent.py  
- Tool service execution logging in service.py
- Full request-response chain visibility for debugging
- Performance tracking and metrics collection

Phase {phase_num}/2 of execution chain logging implementation

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>"""
        
        success, output = self.run_command(["git", "commit", "-m", commit_message])
        
        if success:
            self.print_colored(f"Phase {phase_num} committed successfully!", "green")
            return True
        else:
            self.print_colored(f"Phase {phase_num} commit failed: {output}", "red")
            return False
    
    def execute_all_phases(self) -> None:
        """Execute all phases sequentially"""
        self.print_colored("Executing both phases sequentially...", "cyan")
        
        for phase_num in [1, 2]:
            success = self.execute_phase(phase_num)
            if not success:
                self.print_colored(f"Stopping at phase {phase_num} due to failure.", "red")
                return
            print()
        
        # Final message
        self.print_colored("Both phases completed! Execution chain logging implementation finished.", "green")
        self.print_colored("Ready to push with: git push origin feat_e2e_test", "cyan")
    
    def show_menu(self) -> str:
        """Show interactive menu and get user choice"""
        self.print_colored("Git Two-Phase Commit - Interactive Mode", "cyan")
        self.print_colored("=" * 40, "cyan")
        print("Available phases:")
        for num, phase in self.phases.items():
            print(f"{num} - {phase['name']}")
        print()
        print("Special commands:")
        print("all - Execute both phases sequentially")
        print("copy <target_dir> - Copy files to external directory")
        print()
        
        choice = input("Enter choice: ").strip()
        return choice


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Git Two-Phase Commit Script")
    parser.add_argument("command", nargs="?", help="Phase number (1-2), 'all', or 'copy'")
    parser.add_argument("target_dir", nargs="?", help="Target directory for copy mode")
    args = parser.parse_args()
    
    # Change to script's parent directory (project root)
    script_dir = Path(__file__).parent.parent
    os.chdir(script_dir)
    
    git_commit = GitTwoPhaseCommit()
    
    # Handle copy mode
    if args.command == "copy":
        if not args.target_dir:
            git_commit.print_colored("Target directory required for copy mode", "red")
            git_commit.print_colored("Usage: python git_push_plan.py copy <target_dir>", "cyan")
            return 1
        
        success = git_commit.execute_copy_mode(args.target_dir)
        return 0 if success else 1
    
    # Get command from args or interactive menu
    command = args.command if args.command else git_commit.show_menu()
    
    # Handle copy command from interactive mode
    if command.startswith("copy "):
        parts = command.split()
        if len(parts) < 2:
            git_commit.print_colored("Usage: copy <target_dir>", "red")
            return 1
        target_dir = parts[1]
        success = git_commit.execute_copy_mode(target_dir)
        return 0 if success else 1
    
    # Handle phase execution
    if command == "all":
        git_commit.execute_all_phases()
    elif command in ["1", "2"]:
        phase_num = int(command)
        git_commit.execute_phase(phase_num)
    else:
        git_commit.print_colored("Invalid choice. Use 1, 2, 'all', or 'copy <target_dir>'.", "red")
        return 1
    
    print()
    git_commit.print_colored("Git two-phase commit execution completed.", "green")
    return 0


if __name__ == "__main__":
    sys.exit(main())