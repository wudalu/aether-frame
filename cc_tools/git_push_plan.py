#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Git Batch Commit Script for Unpushed Changes
============================================

Simple script to split unpushed changes into 2 commits under 2000 lines each.

🚀 USAGE:
---------
# Interactive Mode
python git_push_plan.py

# Execute Commit 1
python git_push_plan.py 1

# Execute Commit 2  
python git_push_plan.py 2

# Execute Both Commits
python git_push_plan.py all

# Copy files to external directory
python git_push_plan.py copy <target_directory>

"""

import sys
import subprocess
import os
import shutil
from typing import List
import argparse
from pathlib import Path


class GitBatchCommit:
    """Simple git batch commit manager"""
    
    def __init__(self):
        # Hardcoded list of unpushed files - split into 2 batches
        self.commits = {
            1: {
                "name": "Batch 1",
                "description": "feat: first batch of unpushed changes",
                "files": [
                    ".env.example.custom",
                    ".gitignore", 
                    "docs/adk_performance_testing_summary.md",
                    "docs/architecture.md",
                    "docs/dev_plan.md",
                    "src/aether_frame/agents/adk/adk_domain_agent.py",
                    "src/aether_frame/bootstrap.py",
                    "src/aether_frame/common/interaction_logger.py",
                    "src/aether_frame/common/unified_logging.py",
                    "src/aether_frame/config/settings.py",
                    "src/aether_frame/contracts/configs.py",
                    "src/aether_frame/contracts/contexts.py"
                ]
            },
            2: {
                "name": "Batch 2", 
                "description": "feat: second batch of unpushed changes",
                "files": [
                    "src/aether_frame/contracts/requests.py",
                    "src/aether_frame/contracts/responses.py",
                    "src/aether_frame/framework/adk/adk_adapter.py",
                    "src/aether_frame/framework/adk/runner_manager.py",
                    "tests/e2e/test_complete_aiassistant_flow.py",
                    "tests/e2e/test_real_validation.py",
                    "tests/e2e/test_runner_manager_e2e.py",
                    "tests/e2e/test_session_id_propagation_e2e.py",
                    "tests/integration/test_components.py",
                    "tests/integration/test_end_to_end.py",
                    "tests/manual/test_complete_e2e.py",
                    "tests/unit/test_contracts.py"
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
        
        # Copy all files from both commits
        all_files = []
        for commit in self.commits.values():
            all_files.extend(commit["files"])
        
        if not all_files:
            self.print_colored("No files to copy.", "yellow")
            return False
        
        return self.copy_files(target_dir, all_files)
    
    def execute_commit(self, commit_num: int) -> bool:
        """Execute a specific commit"""
        if commit_num not in self.commits:
            self.print_colored(f"Invalid commit number: {commit_num}", "red")
            return False
        
        commit = self.commits[commit_num]
        
        self.print_colored("=" * 60, "magenta")
        self.print_colored(f"Commit {commit_num}: {commit['name']}", "magenta")
        self.print_colored("=" * 60, "magenta")
        
        self.check_status()
        
        # Add files for this commit
        self.add_files(commit["files"])
        
        self.show_commit_preview()
        
        # Confirm commit
        confirm = input(f"Proceed with Commit {commit_num}? (y/n): ").strip().lower()
        if confirm not in ['y', 'yes']:
            self.print_colored(f"Commit {commit_num} cancelled.", "yellow")
            self.run_command(["git", "reset"])
            return False
        
        # Run quality checks
        if not self.run_checks():
            self.run_command(["git", "reset"])
            return False
        
        # Create commit message
        file_list = "\n".join([f"- {f}" for f in commit["files"]])
        commit_message = f"""{commit['description']}

This commit includes:
{file_list}

Commit {commit_num}/2

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>"""
        
        success, output = self.run_command(["git", "commit", "-m", commit_message])
        
        if success:
            self.print_colored(f"Commit {commit_num} committed successfully!", "green")
            return True
        else:
            self.print_colored(f"Commit {commit_num} commit failed: {output}", "red")
            return False
    
    def execute_all_commits(self) -> None:
        """Execute all commits sequentially"""
        if not self.commits:
            self.print_colored("No commits to execute.", "yellow")
            return
        
        self.print_colored("Executing both commits sequentially...", "cyan")
        
        for commit_num in [1, 2]:
            if commit_num in self.commits:
                success = self.execute_commit(commit_num)
                if not success:
                    self.print_colored(f"Stopping at commit {commit_num} due to failure.", "red")
                    return
                print()
        
        # Final message
        self.print_colored("Both commits completed! All unpushed changes have been committed.", "green")
        self.print_colored("Ready to push with: git push origin <branch_name>", "cyan")
    
    def show_menu(self) -> str:
        """Show interactive menu and get user choice"""
        self.print_colored("Git Batch Commit - Interactive Mode", "cyan")
        self.print_colored("=" * 40, "cyan")
        print("Available commits:")
        for num, commit in self.commits.items():
            file_count = len(commit["files"])
            print(f"{num} - {commit['name']} ({file_count} files)")
        print()
        print("Special commands:")
        print("all - Execute both commits sequentially")
        print("copy <target_dir> - Copy files to external directory")
        print()
        
        choice = input("Enter choice: ").strip()
        return choice


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Git Batch Commit Script")
    parser.add_argument("command", nargs="?", help="Commit number (1-2), 'all', or 'copy'")
    parser.add_argument("target_dir", nargs="?", help="Target directory for copy mode")
    args = parser.parse_args()
    
    # Change to script's parent directory (project root)
    script_dir = Path(__file__).parent.parent
    os.chdir(script_dir)
    
    git_commit = GitBatchCommit()
    
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
    
    # Handle commit execution
    if command == "all":
        git_commit.execute_all_commits()
    elif command in ["1", "2"]:
        commit_num = int(command)
        git_commit.execute_commit(commit_num)
    else:
        git_commit.print_colored("Invalid choice. Use 1, 2, 'all', or 'copy <target_dir>'.", "red")
        return 1
    
    print()
    git_commit.print_colored("Git batch commit execution completed.", "green")
    return 0


if __name__ == "__main__":
    sys.exit(main())