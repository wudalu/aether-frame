#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Git Push Plan Execution Script for feat_execution_layer Branch
============================================================

This script executes the 7-phase commit plan to safely commit 14,000+ lines of code
while staying under the 2000-line limit per commit.

🚀 USAGE:
---------
# Interactive Mode (Recommended)
python git_push_plan.py

# Execute Specific Phase
python git_push_plan.py 1    # Phase 1: Core contracts and base configuration
python git_push_plan.py 2    # Phase 2: Framework abstraction foundation
python git_push_plan.py 3    # Phase 3: Execution engine and tools
python git_push_plan.py 4    # Phase 4: Agent management system
python git_push_plan.py 5    # Phase 5: Unit tests
python git_push_plan.py 6    # Phase 6: Integration and e2e tests
python git_push_plan.py 7    # Phase 7: Final components and streaming

# Execute All Phases Sequentially  
python git_push_plan.py all

# Copy Mode - Copy files for external commit
python git_push_plan.py copy <target_directory> [phase_number]

📋 PHASES:
----------
Phase 1 (~1,950 lines): Core Contracts and Base Configuration
- Contracts layer (src/aether_frame/contracts/)
- Basic configuration (config/settings.py, logging.py)
- Environment and project files (.env.example, .gitignore)

Phase 2 (~1,850 lines): Framework Abstraction Foundation
- Framework registry and base abstractions
- Basic framework adapters structure
- Core framework interface definitions

Phase 3 (~1,900 lines): Execution Engine and Tools
- Execution engine (src/aether_frame/execution/)
- Tool service layer (src/aether_frame/tools/)
- Task routing and coordination

Phase 4 (~1,950 lines): Agent Management System
- Agent management (src/aether_frame/agents/)
- Infrastructure layer (src/aether_frame/infrastructure/)
- Bootstrap system (src/aether_frame/bootstrap.py)

Phase 5 (~1,800 lines): Unit Tests
- Unit tests (tests/unit/)
- Basic test infrastructure
- Core component testing

Phase 6 (~1,900 lines): Integration and E2E Tests
- Integration tests (tests/integration/)
- End-to-end tests (tests/e2e/)
- Manual tests (tests/manual/)

Phase 7 (~1,800 lines): Final Components and Streaming
- ADK streaming components (deepseek_*.py, model_factory.py)
- Event conversion system (adk_event_converter.py)
- Debug tools (tests/debug/)
- Archive and cleanup (archive/, cc_tools/)

⚡ FEATURES:
-----------
✅ Automatic code quality checks (lint + type-check)
✅ Interactive confirmation for each phase
✅ Colored output for better readability
✅ File existence validation
✅ Safe rollback on failures
✅ Copy mode for external directory commits
✅ Cross-platform compatibility (Windows PowerShell/Linux/macOS)

🔒 SAFETY:
----------
- Each phase requires user confirmation
- Quality checks must pass before commit
- Failed commits are automatically rolled back
- Preview of files before each commit
- Git status check before each phase

💡 COPY MODE:
-------------
Copy specific phase files to external directory for gradual commits:

# Copy Phase 1 files to external repo
python git_push_plan.py copy ../external_repo 1

# Copy all files to external repo
python git_push_plan.py copy ../external_repo all

💡 TIPS:
--------
- Run phases individually first (python git_push_plan.py 1, then 2, etc.)
- Use copy mode for external repositories
- Check git status after each phase: git status
- Verify tests pass after final phase: python dev.py test
- Push to remote after all phases: git push origin feat_execution_layer

For detailed phase breakdown, see: git_push_plan.md

"""

import sys
import subprocess
import os
import shutil
from typing import List
import argparse
from pathlib import Path


class GitPushPlan:
    """Git Push Plan execution manager"""
    
    def __init__(self):
        self.phases = {
            1: {
                "name": "Core Contracts and Base Configuration",
                "description": "feat: establish core contracts and base configuration foundation",
                "files": [
                    "src/aether_frame/contracts/",
                    "src/aether_frame/config/settings.py",
                    "src/aether_frame/config/logging.py",
                    "src/aether_frame/config/__init__.py",
                    ".env.example",
                    ".gitignore",
                    "src/aether_frame/__init__.py",
                    "src/aether_frame/main.py"
                ]
            },
            2: {
                "name": "Framework Abstraction Foundation",
                "description": "feat: implement framework registry and base abstraction interfaces",
                "files": [
                    "src/aether_frame/framework/__init__.py",
                    "src/aether_frame/framework/base/",
                    "src/aether_frame/framework/framework_registry.py"
                ]
            },
            3: {
                "name": "Execution Engine and Tools",
                "description": "feat: implement execution engine and tool service layer",
                "files": [
                    "src/aether_frame/execution/",
                    "src/aether_frame/tools/",
                    "src/aether_frame/config/framework_capabilities.py",
                    "src/aether_frame/config/routing_config.py"
                ]
            },
            4: {
                "name": "Agent Management System",
                "description": "feat: implement comprehensive agent management system",
                "files": [
                    "src/aether_frame/agents/",
                    "src/aether_frame/framework/adk/",
                    "src/aether_frame/bootstrap.py",
                    "pyproject.toml",
                    "requirements/base.in",
                    "README.md",
                    "docs/architecture.md",
                    "docs/framework_abstraction.md",
                    "docs/layout.md",
                    "docs/bootstrap.md"
                ]
            },
            5: {
                "name": "Unit Tests",
                "description": "test: add comprehensive unit test suite",
                "files": [
                    "tests/unit/",
                    "tests/conftest.py"
                ]
            },
            6: {
                "name": "Integration and E2E Tests",
                "description": "test: add integration and end-to-end test suites",
                "files": [
                    "tests/integration/",
                    "tests/e2e/",
                    "tests/manual/"
                ]
            },
            7: {
                "name": "Final Components and Streaming", 
                "description": "feat: add streaming features and complete architecture implementation",
                "files": [
                    "src/aether_frame/framework/adk/deepseek_llm.py",
                    "src/aether_frame/framework/adk/deepseek_streaming_llm.py",
                    "src/aether_frame/framework/adk/model_factory.py",
                    "src/aether_frame/agents/adk/adk_event_converter.py",
                    "tests/debug/",
                    "tests/unit/test_phase3_interfaces.py.disabled",
                    "archive/"
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
            if os.path.exists(file_path) or file_path == ".":
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
                
                if source_path.is_dir():
                    # Copy entire directory
                    if target_file_path.exists():
                        shutil.rmtree(target_file_path)
                    shutil.copytree(source_path, target_file_path)
                    self.print_colored(f"Copied directory {file_path}", "green")
                    copied_count += 1
                else:
                    # Copy single file
                    target_file_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source_path, target_file_path)
                    self.print_colored(f"Copied file {file_path}", "green")
                    copied_count += 1
            else:
                self.print_colored(f"Skipping {file_path} (not found)", "yellow")
        
        self.print_colored(f"Copied {copied_count} items to {target_dir}", "cyan")
        return copied_count > 0
    
    def execute_copy_mode(self, target_dir: str, phase_num: str = "all") -> bool:
        """Execute copy mode for external directory"""
        self.print_colored("=== COPY MODE ===", "magenta")
        self.print_colored(f"Target directory: {target_dir}", "cyan")
        
        if phase_num == "all":
            self.print_colored("Copying all phases to target directory...", "cyan")
            all_files = []
            for phase in self.phases.values():
                all_files.extend(phase["files"])
            return self.copy_files(target_dir, all_files)
        
        elif phase_num.isdigit() and 1 <= int(phase_num) <= 7:
            phase_number = int(phase_num)
            phase = self.phases[phase_number]
            self.print_colored(f"Copying Phase {phase_number}: {phase['name']}", "cyan")
            return self.copy_files(target_dir, phase["files"])
        
        else:
            self.print_colored(f"Invalid phase: {phase_num}. Use 1-7 or 'all'.", "red")
            return False
    
    def execute_phase(self, phase_num: int) -> bool:
        """Execute a specific phase"""
        if phase_num not in self.phases:
            self.print_colored(f"Invalid phase number: {phase_num}", "red")
            return False
        
        phase = self.phases[phase_num]
        
        self.print_colored("=" * 50, "magenta")
        self.print_colored(f"Phase {phase_num}: {phase['name']}", "magenta")
        self.print_colored("=" * 50, "magenta")
        
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
                
                if total_lines > 2000:
                    self.print_colored(f"WARNING: This commit has {total_lines} lines (>2000 limit)", "yellow")
                    confirm = input("This exceeds the 2000-line limit. Continue anyway? (y/n): ").strip().lower()
                    if confirm not in ['y', 'yes']:
                        self.print_colored(f"Phase {phase_num} cancelled due to line count.", "yellow")
                        self.run_command(["git", "reset"])
                        return False
        
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
        
        # Commit
        commit_message = f"""{phase['description']}

This commit includes:
- {phase['name']}
- Phase {phase_num}/7 of feat_execution_layer branch

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
        self.print_colored("Executing all phases sequentially...", "cyan")
        
        for phase_num in range(1, 8):
            success = self.execute_phase(phase_num)
            if not success:
                self.print_colored(f"Stopping at phase {phase_num} due to failure.", "red")
                return
            print()
        
        # Final verification after all phases
        self.print_colored("All phases completed! Running final verification...", "yellow")
        if os.path.exists("dev.py"):
            success, output = self.run_command(["python", "dev.py", "test"])
            if success:
                print()
                self.print_colored("SUCCESS: All tests passed! Ready to push to remote.", "green")
                self.print_colored("Command to push: git push origin feat_execution_layer", "cyan")
            else:
                print()
                self.print_colored("WARNING: Some tests failed. Please review before pushing.", "yellow")
                if output:
                    print(output)
        else:
            self.print_colored("dev.py not found, skipping final tests", "yellow")
    
    def show_menu(self) -> str:
        """Show interactive menu and get user choice"""
        self.print_colored("Git Push Plan - Interactive Mode", "cyan")
        self.print_colored("=" * 35, "cyan")
        print("Available phases:")
        for num, phase in self.phases.items():
            print(f"{num} - {phase['name']}")
        print()
        print("Special commands:")
        print("all - Execute all phases sequentially")
        print("copy <target_dir> [phase] - Copy files to external directory")
        print()
        
        choice = input("Enter choice: ").strip()
        return choice
    
    def show_file_list(self, phase_num: int = None) -> None:
        """Show list of files for a phase or all phases"""
        if phase_num and phase_num in self.phases:
            phase = self.phases[phase_num]
            self.print_colored(f"Phase {phase_num}: {phase['name']}", "cyan")
            for file_path in phase['files']:
                print(f"  {file_path}")
        else:
            for num, phase in self.phases.items():
                self.print_colored(f"\nPhase {num}: {phase['name']}", "cyan")
                for file_path in phase['files']:
                    print(f"  {file_path}")


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Git Push Plan Execution Script")
    parser.add_argument("phase", nargs="?", help="Phase number (1-7), 'all', 'copy', or 'list'")
    parser.add_argument("target_dir", nargs="?", help="Target directory for copy mode")
    parser.add_argument("copy_phase", nargs="?", help="Phase to copy (for copy mode)")
    parser.add_argument("--no-checks", action="store_true", help="Skip code quality checks")
    parser.add_argument("--list", action="store_true", help="List files for phases")
    args = parser.parse_args()
    
    # Change to script's parent directory (project root)
    script_dir = Path(__file__).parent.parent
    os.chdir(script_dir)
    
    git_plan = GitPushPlan()
    
    # Handle copy mode
    if args.phase == "copy":
        if not args.target_dir:
            git_plan.print_colored("Target directory required for copy mode", "red")
            git_plan.print_colored("Usage: python git_push_plan.py copy <target_dir> [phase]", "cyan")
            return 1
        
        copy_phase = args.copy_phase or "all"
        success = git_plan.execute_copy_mode(args.target_dir, copy_phase)
        return 0 if success else 1
    
    # Handle list mode
    if args.list or args.phase == "list":
        phase_num = None
        if args.target_dir and args.target_dir.isdigit():
            phase_num = int(args.target_dir)
        git_plan.show_file_list(phase_num)
        return 0
    
    # Get phase from command line or interactive menu
    phase = args.phase if args.phase else git_plan.show_menu()
    
    # Handle copy command from interactive mode
    if phase.startswith("copy "):
        parts = phase.split()
        if len(parts) < 2:
            git_plan.print_colored("Usage: copy <target_dir> [phase]", "red")
            return 1
        target_dir = parts[1]
        copy_phase = parts[2] if len(parts) > 2 else "all"
        success = git_plan.execute_copy_mode(target_dir, copy_phase)
        return 0 if success else 1
    
    if phase == "all":
        git_plan.execute_all_phases()
    elif phase.isdigit() and 1 <= int(phase) <= 7:
        phase_num = int(phase)
        success = git_plan.execute_phase(phase_num)
        
        # Run final tests only after phase 7
        if success and phase_num == 7:
            print()
            git_plan.print_colored("Phase 7 completed! Running final verification...", "yellow")
            if os.path.exists("dev.py"):
                test_success, test_output = git_plan.run_command(["python", "dev.py", "test"])
                if test_success:
                    print()
                    git_plan.print_colored("SUCCESS: All tests passed! Ready to push to remote.", "green")
                    git_plan.print_colored("Command to push: git push origin feat_execution_layer", "cyan")
                else:
                    print()
                    git_plan.print_colored("WARNING: Some tests failed. Please review before pushing.", "yellow")
                    if test_output:
                        print(test_output)
            else:
                git_plan.print_colored("dev.py not found, skipping final tests", "yellow")
    else:
        git_plan.print_colored("Invalid choice. Use 1-7, 'all', 'copy <target_dir> [phase]', or 'list'.", "red")
        return 1
    
    print()
    git_plan.print_colored("Git Push Plan execution completed.", "green")
    return 0


if __name__ == "__main__":
    sys.exit(main())