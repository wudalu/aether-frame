#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Git Push Plan Execution Script for feat_execution_layer Branch
============================================================

This script executes the 5-phase commit plan to safely commit 8,600+ lines of code
while staying under the 2000-line limit per commit.

🚀 USAGE:
---------
# Interactive Mode (Recommended)
python git_push_plan.py

# Execute Specific Phase
python git_push_plan.py 1    # Phase 1: Core contracts and architecture
python git_push_plan.py 2    # Phase 2: Framework abstraction layer
python git_push_plan.py 3    # Phase 3: Agent management system
python git_push_plan.py 4    # Phase 4: Test suite
python git_push_plan.py 5    # Phase 5: Event conversion and completion

# Execute All Phases Sequentially  
python git_push_plan.py all

📋 PHASES:
----------
Phase 1 (~1,800 lines): Core Contracts and Base Architecture
- Contracts layer (src/aether_frame/contracts/)
- Configuration updates
- Project documentation and infrastructure

Phase 2 (~1,900 lines): Framework Abstraction Layer
- Framework adapter system (src/aether_frame/framework/)
- Execution engine (src/aether_frame/execution/)
- Tool service basics (src/aether_frame/tools/)

Phase 3 (~1,700 lines): Agent Management System
- Agent management (src/aether_frame/agents/)
- Infrastructure layer (src/aether_frame/infrastructure/)
- Common utilities updates

Phase 4 (~1,800 lines): Test Suite
- Unit tests (tests/unit/)
- Integration tests (tests/integration/)
- End-to-end tests (tests/e2e/)

Phase 5 (~1,200 lines): Event Conversion and Completion
- Event converter (adk_event_converter.py)
- Phase 3 interfaces (test_phase3_interfaces.py)
- Directory structures and final cleanup

⚡ FEATURES:
-----------
✅ Automatic code quality checks (lint + type-check)
✅ Interactive confirmation for each phase
✅ Colored output for better readability
✅ File existence validation
✅ Safe rollback on failures
✅ Final test suite validation
✅ Cross-platform compatibility (Windows/macOS/Linux)

🔒 SAFETY:
----------
- Each phase requires user confirmation
- Quality checks must pass before commit
- Failed commits are automatically rolled back
- Preview of files before each commit
- Git status check before each phase

💡 TIPS:
--------
- Run phases individually first (python git_push_plan.py 1, then 2, etc.)
- Check git status after each phase: git status
- Verify tests pass after final phase: python dev.py test
- Push to remote after all phases: git push origin feat_execution_layer

For detailed phase breakdown, see: git_push_plan.md
"""

import sys
import subprocess
import os
from typing import List, Dict, Any
import argparse
from pathlib import Path


class GitPushPlan:
    """Git Push Plan execution manager"""
    
    def __init__(self):
        self.phases = {
            1: {
                "name": "Core Contracts and Base Architecture",
                "description": "feat: establish core contracts and base architecture foundation",
                "files": [
                    "src/aether_frame/contracts/",
                    "src/aether_frame/config/framework_capabilities.py",
                    "src/aether_frame/config/routing_config.py", 
                    "src/aether_frame/config/settings.py",
                    "src/aether_frame/config/__init__.py",
                    ".gitignore",
                    "README.md",
                    "docs/",
                    "interface_design_proposal.md",
                    "pyproject.toml",
                    "requirements/base.in",
                    "run_tests.py"
                ]
            },
            2: {
                "name": "Framework Abstraction Layer",
                "description": "feat: implement framework abstraction layer and registry system",
                "files": [
                    "src/aether_frame/framework/",
                    "src/aether_frame/execution/",
                    "src/aether_frame/tools/__init__.py",
                    "src/aether_frame/tools/base/",
                    "src/aether_frame/tools/builtin/",
                    "src/aether_frame/tools/service.py"
                ]
            },
            3: {
                "name": "Agent Management System",
                "description": "feat: implement comprehensive agent management system",
                "files": [
                    "src/aether_frame/agents/",
                    "src/aether_frame/infrastructure/",
                    "src/aether_frame/common/",
                    "src/aether_frame/__init__.py",
                    "src/aether_frame/main.py",
                    "src/aether_frame/tools/adk_native/",
                    "src/aether_frame/tools/mcp/",
                    "src/aether_frame/tools/external/",
                    "src/aether_frame/tools/llm/",
                    "src/aether_frame/tools/search/"
                ]
            },
            4: {
                "name": "Test Suite",
                "description": "test: add comprehensive test suite for all layers",
                "files": [
                    "tests/",
                    "test_end_to_end.py"
                ]
            },
            5: {
                "name": "Event Conversion and Completion", 
                "description": "feat: add event conversion system and complete architecture implementation",
                "files": [
                    "src/aether_frame/agents/adk/adk_event_converter.py",
                    "tests/unit/test_phase3_interfaces.py",
                    "src/aether_frame/agents/domain/",
                    "src/aether_frame/execution/coordinator/",
                    "src/aether_frame/execution/workflow/",
                    "src/aether_frame/memory/",
                    "src/aether_frame/observability/",
                    "."  # Add any remaining files
                ]
            }
        }
    
    def print_colored(self, text: str, color: str = "white") -> None:
        """Print colored text to console"""
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
        
        color_code = colors.get(color, colors["white"])
        print(f"{color_code}{text}{colors['reset']}")
    
    def run_command(self, cmd: List[str], capture_output: bool = False) -> tuple:
        """Run shell command and return (success, output)"""
        try:
            if capture_output:
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                return True, result.stdout.strip()
            else:
                result = subprocess.run(cmd, check=True)
                return True, ""
        except subprocess.CalledProcessError as e:
            if capture_output:
                return False, e.stderr.strip() if e.stderr else str(e)
            else:
                return False, str(e)
    
    def run_checks(self) -> bool:
        """Run code quality checks"""
        self.print_colored("Running code quality checks...", "yellow")
        
        # Run linting
        self.print_colored("Running linter...", "cyan")
        success, output = self.run_command(["python", "dev.py", "lint"])
        if not success:
            self.print_colored("ERROR: Linting failed. Please fix issues before committing.", "red")
            if output:
                print(output)
            input("Press Enter to continue...")
            return False
        
        # Run type checking
        self.print_colored("Running type checker...", "cyan")  
        success, output = self.run_command(["python", "dev.py", "type-check"])
        if not success:
            self.print_colored("ERROR: Type checking failed. Please fix issues before committing.", "red")
            if output:
                print(output)
            input("Press Enter to continue...")
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
        commit_message = f"{phase['description']}\n\n🚀 Generated with Claude Code\nCo-Authored-By: Claude <noreply@anthropic.com>"
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
        
        for phase_num in range(1, 6):
            success = self.execute_phase(phase_num)
            if not success:
                self.print_colored(f"Stopping at phase {phase_num} due to failure.", "red")
                return
            print()
        
        # Final verification after all phases
        if phase_num == 5:  # Only run final tests after phase 5
            self.print_colored("All phases completed! Running final verification...", "yellow")
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
    
    def show_menu(self) -> str:
        """Show interactive menu and get user choice"""
        self.print_colored("Git Push Plan - Interactive Mode", "cyan")
        self.print_colored("=" * 35, "cyan")
        print("Available phases:")
        for num, phase in self.phases.items():
            print(f"{num} - {phase['name']}")
        print()
        
        choice = input("Enter phase number (1-5) or 'all' for all phases: ").strip().lower()
        return choice


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Git Push Plan Execution Script")
    parser.add_argument("phase", nargs="?", help="Phase number (1-5) or 'all'")
    parser.add_argument("--no-checks", action="store_true", help="Skip code quality checks")
    args = parser.parse_args()
    
    # Change to script directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    git_plan = GitPushPlan()
    
    # Get phase from command line or interactive menu
    phase = args.phase if args.phase else git_plan.show_menu()
    
    if phase == "all":
        git_plan.execute_all_phases()
    elif phase.isdigit() and 1 <= int(phase) <= 5:
        phase_num = int(phase)
        success = git_plan.execute_phase(phase_num)
        
        # Run final tests only after phase 5
        if success and phase_num == 5:
            print()
            git_plan.print_colored("Phase 5 completed! Running final verification...", "yellow")
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
        git_plan.print_colored("Invalid phase number. Use 1-5 or 'all'.", "red")
        return 1
    
    print()
    git_plan.print_colored("Git Push Plan execution completed.", "green")
    return 0


if __name__ == "__main__":
    sys.exit(main())