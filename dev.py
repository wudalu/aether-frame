#!/usr/bin/env python3
"""
Development tools for Aether Frame.
A complete replacement for Makefile using pure Python.
"""

import os
import sys
import shutil
import subprocess
import argparse
from pathlib import Path
from typing import List, Optional


class DevTools:
    """Development tools manager for Aether Frame."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.src_dir = self.project_root / "src"
        self.tests_dir = self.project_root / "tests"
        self.requirements_dir = self.project_root / "requirements"
        
    def run_command(self, cmd: List[str], cwd: Optional[Path] = None) -> int:
        """Run a shell command and return exit code."""
        if cwd is None:
            cwd = self.project_root
        
        print(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, cwd=cwd)
        return result.returncode
    
    def help(self):
        """Show available commands."""
        print("Available commands:")
        print("  venv-init       Create and show activation for virtual environment")
        print("  venv-setup      Set up virtual environment")
        print("  venv-activate   Show activation command")
        print("  venv-auto-activate Auto-activate virtual environment (Windows)")
        print("  venv-status     Check virtual environment status")
        print("  install         Install production dependencies")
        print("  dev-install     Install development dependencies") 
        print("  compile-deps    Compile requirements files")
        print("  update-deps     Update and compile requirements files")
        print("  clean           Clean up cache and temporary files")
        print("  test            Run all tests")
        print("  test-unit       Run unit tests only")
        print("  test-integration Run integration tests only")
        print("  test-e2e        Run end-to-end tests only")
        print("  test-coverage   Run tests with coverage")
        print("  lint            Run linting checks")
        print("  format          Format code")
        print("  type-check      Run type checking")
        print("  setup-dev       Set up development environment")
        print("  version         Show current version")
        
    def venv_init(self):
        """Create virtual environment and show activation command."""
        exit_code = self.venv_setup()
        if exit_code == 0:
            print("\n" + "="*50)
            self.venv_activate()
        return exit_code
        
    def venv_setup(self):
        """Set up virtual environment."""
        venv_path = self.project_root / ".venv"
        
        if venv_path.exists():
            print(f"Virtual environment already exists at {venv_path}")
            return 0
            
        print("Creating virtual environment...")
        exit_code = self.run_command([
            sys.executable, "-m", "venv", str(venv_path)
        ])
        
        if exit_code == 0:
            print(f"Virtual environment created at {venv_path}")
            print("To activate:")
            if os.name == 'nt':  # Windows
                print(f"  {venv_path}\\Scripts\\Activate.ps1")
            else:  # Unix/Linux/macOS
                print(f"  source {venv_path}/bin/activate")
        
        return exit_code
        
    def venv_activate(self):
        """Show activation command for virtual environment."""
        venv_path = self.project_root / ".venv"
        
        if not venv_path.exists():
            print("Virtual environment not found. Run 'python dev.py venv-setup' first.")
            return 1
            
        print("To activate virtual environment:")
        if os.name == 'nt':  # Windows
            print(f"  {venv_path}\\Scripts\\Activate.ps1")
        else:  # Unix/Linux/macOS  
            print(f"  source {venv_path}/bin/activate")
        
        return 0
    
    def venv_auto_activate(self):
        """Automatically activate virtual environment (Windows PowerShell only)."""
        if os.name != 'nt':
            print("Auto-activation only supported on Windows PowerShell")
            return 1
            
        venv_path = self.project_root / ".venv"
        
        if not venv_path.exists():
            print("Virtual environment not found. Creating it first...")
            exit_code = self.venv_setup()
            if exit_code != 0:
                return exit_code
        
        activate_script = venv_path / "Scripts" / "Activate.ps1"
        
        if not activate_script.exists():
            print(f"Activation script not found at {activate_script}")
            return 1
        
        print("Activating virtual environment...")
        
        # Try to execute the PowerShell activation script
        try:
            exit_code = self.run_command([
                "powershell", "-ExecutionPolicy", "Bypass", 
                "-File", str(activate_script)
            ])
            
            if exit_code == 0:
                print("✓ Virtual environment activated successfully!")
                print("Note: The activation is only effective in the current PowerShell session.")
            else:
                print("✗ Failed to activate virtual environment")
                print("Try manually running:")
                print(f"  {activate_script}")
                
            return exit_code
            
        except Exception as e:
            print(f"Error activating virtual environment: {e}")
            print("Try manually running:")
            print(f"  {activate_script}")
            return 1
        
    def venv_status(self):
        """Check virtual environment status."""
        venv_path = self.project_root / ".venv"
        
        print("=== Virtual Environment Status ===")
        
        # Check if .venv directory exists
        if venv_path.exists():
            print(f"✓ Virtual environment exists at: {venv_path}")
        else:
            print(f"✗ Virtual environment not found at: {venv_path}")
            print("Run 'python dev.py venv-init' to create it.")
            return 1
        
        # Check current Python interpreter
        current_python = sys.executable
        expected_python = venv_path / ("Scripts/python.exe" if os.name == 'nt' else "bin/python")
        
        print(f"\nCurrent Python interpreter: {current_python}")
        print(f"Expected venv Python: {expected_python}")
        
        # Check if we're using the correct Python
        if str(expected_python) in current_python or current_python == str(expected_python):
            print("✓ Using project virtual environment")
            is_correct_venv = True
        else:
            print("✗ NOT using project virtual environment")
            is_correct_venv = False
        
        # Check VIRTUAL_ENV environment variable
        virtual_env = os.environ.get('VIRTUAL_ENV')
        if virtual_env:
            print(f"\nVIRTUAL_ENV: {virtual_env}")
            if str(venv_path) in virtual_env:
                print("✓ VIRTUAL_ENV points to project venv")
            else:
                print("✗ VIRTUAL_ENV points to different location")
                is_correct_venv = False
        else:
            print("\nVIRTUAL_ENV: Not set")
            print("✗ Virtual environment may not be activated")
            is_correct_venv = False
        
        # Show activation command if not in correct venv
        if not is_correct_venv:
            print(f"\nTo activate the correct virtual environment:")
            if os.name == 'nt':  # Windows
                print(f"  {venv_path}\\Scripts\\Activate.ps1")
            else:  # Unix/Linux/macOS
                print(f"  source {venv_path}/bin/activate")
        
        print(f"\nPython version: {sys.version}")
        
        # Check if project packages are installed
        try:
            import importlib.util
            spec = importlib.util.find_spec("aether_frame")
            if spec:
                print("✓ Project package (aether_frame) is available")
            else:
                print("✗ Project package (aether_frame) not found")
                print("Run 'python dev.py dev-install' to install in development mode")
        except Exception:
            print("? Could not check project package installation")
        
        return 0 if is_correct_venv else 1
        
    def compile_deps(self):
        """Compile requirements files."""
        print("Compiling requirements...")
        
        base_in = self.requirements_dir / "base.in"
        dev_in = self.requirements_dir / "dev.in"
        
        if not base_in.exists():
            print(f"Error: {base_in} not found")
            return 1
            
        if not dev_in.exists():
            print(f"Error: {dev_in} not found")
            return 1
            
        # Compile base requirements
        exit_code = self.run_command([
            sys.executable, "-m", "pip", "install", "pip-tools"
        ])
        if exit_code != 0:
            return exit_code
            
        exit_code = self.run_command([
            "pip-compile", str(base_in)
        ])
        if exit_code != 0:
            return exit_code
            
        # Compile dev requirements
        exit_code = self.run_command([
            "pip-compile", str(dev_in)
        ])
        
        return exit_code
        
    def update_deps(self):
        """Update and compile requirements files."""
        print("Updating and compiling requirements...")
        
        base_in = self.requirements_dir / "base.in"
        dev_in = self.requirements_dir / "dev.in"
        
        if not base_in.exists() or not dev_in.exists():
            print("Error: requirements files not found")
            return 1
            
        # Update base requirements
        exit_code = self.run_command([
            "pip-compile", "--upgrade", str(base_in)
        ])
        if exit_code != 0:
            return exit_code
            
        # Update dev requirements
        exit_code = self.run_command([
            "pip-compile", "--upgrade", str(dev_in)
        ])
        
        return exit_code
        
    def install(self):
        """Install production dependencies."""
        print("Installing production dependencies...")
        
        base_txt = self.requirements_dir / "base.txt"
        if not base_txt.exists():
            print("Error: base.txt not found. Run 'python dev.py compile-deps' first.")
            return 1
            
        return self.run_command([
            sys.executable, "-m", "pip", "install", "-r", str(base_txt)
        ])
        
    def dev_install(self):
        """Install development dependencies."""
        print("Installing development dependencies...")
        
        base_txt = self.requirements_dir / "base.txt"
        dev_txt = self.requirements_dir / "dev.txt"
        
        if not base_txt.exists() or not dev_txt.exists():
            print("Error: requirements files not found. Run 'python dev.py compile-deps' first.")
            return 1
            
        # Install requirements
        exit_code = self.run_command([
            sys.executable, "-m", "pip", "install", 
            "-r", str(base_txt), "-r", str(dev_txt)
        ])
        if exit_code != 0:
            return exit_code
            
        # Install package in editable mode
        return self.run_command([
            sys.executable, "-m", "pip", "install", "-e", "."
        ])
        
    def test(self):
        """Run all tests."""
        print("Running all tests...")
        return self.run_command([
            sys.executable, "-m", "pytest", str(self.tests_dir), "-v"
        ])
        
    def test_unit(self):
        """Run unit tests only."""
        print("Running unit tests...")
        return self.run_command([
            sys.executable, "-m", "pytest", str(self.tests_dir / "unit"), "-v"
        ])
        
    def test_integration(self):
        """Run integration tests only."""
        print("Running integration tests...")
        return self.run_command([
            sys.executable, "-m", "pytest", str(self.tests_dir / "integration"), "-v"
        ])
        
    def test_e2e(self):
        """Run end-to-end tests only."""
        print("Running end-to-end tests...")
        return self.run_command([
            sys.executable, "-m", "pytest", str(self.tests_dir / "e2e"), "-v"
        ])
        
    def test_coverage(self):
        """Run tests with coverage."""
        print("Running tests with coverage...")
        return self.run_command([
            sys.executable, "-m", "pytest", str(self.tests_dir), 
            "--cov=src/aether_frame", "--cov-report=html", "--cov-report=term-missing"
        ])
        
    def lint(self):
        """Run linting checks."""
        print("Running linting checks...")
        
        # Run flake8
        exit_code = self.run_command([
            sys.executable, "-m", "flake8", str(self.src_dir), str(self.tests_dir)
        ])
        if exit_code != 0:
            return exit_code
            
        # Check black formatting
        exit_code = self.run_command([
            sys.executable, "-m", "black", "--check", str(self.src_dir), str(self.tests_dir)
        ])
        if exit_code != 0:
            return exit_code
            
        # Check isort
        exit_code = self.run_command([
            sys.executable, "-m", "isort", "--check-only", str(self.src_dir), str(self.tests_dir)
        ])
        
        return exit_code
        
    def format(self):
        """Format code."""
        print("Formatting code...")
        
        # Run black
        exit_code = self.run_command([
            sys.executable, "-m", "black", str(self.src_dir), str(self.tests_dir)
        ])
        if exit_code != 0:
            return exit_code
            
        # Run isort
        exit_code = self.run_command([
            sys.executable, "-m", "isort", str(self.src_dir), str(self.tests_dir)
        ])
        
        return exit_code
        
    def type_check(self):
        """Run type checking."""
        print("Running type checks...")
        return self.run_command([
            sys.executable, "-m", "mypy", str(self.src_dir / "aether_frame")
        ])
        
    def setup_dev(self):
        """Set up development environment."""
        print("Setting up development environment...")
        
        # First install development dependencies
        exit_code = self.dev_install()
        if exit_code != 0:
            return exit_code
            
        # Copy .env file if it doesn't exist
        env_example = self.project_root / ".env.example"
        env_file = self.project_root / ".env"
        
        if env_example.exists() and not env_file.exists():
            shutil.copy2(env_example, env_file)
            print("Created .env file from template")
            
        # Create logs directory
        logs_dir = self.project_root / "logs"
        logs_dir.mkdir(exist_ok=True)
        
        print("Development environment ready!")
        return 0
        
    def clean(self):
        """Clean up cache and temporary files."""
        print("Cleaning up...")
        
        patterns_to_remove = [
            "**/__pycache__",
            "**/*.pyc",
            "**/*.pyo", 
            "**/*.orig",
            ".coverage",
            "**/*.egg-info",
            "**/.pytest_cache",
            "**/.mypy_cache"
        ]
        
        dirs_to_remove = [
            "build",
            "dist", 
            "htmlcov"
        ]
        
        # Remove files matching patterns
        for pattern in patterns_to_remove:
            for path in self.project_root.rglob(pattern.replace("**/", "")):
                if path.is_file():
                    path.unlink()
                    print(f"Removed file: {path}")
                elif path.is_dir():
                    shutil.rmtree(path, ignore_errors=True)
                    print(f"Removed directory: {path}")
                    
        # Remove specific directories
        for dir_name in dirs_to_remove:
            dir_path = self.project_root / dir_name
            if dir_path.exists():
                shutil.rmtree(dir_path, ignore_errors=True)
                print(f"Removed directory: {dir_path}")
                
        print("Cleanup completed!")
        return 0
        
    def version(self):
        """Show current version."""
        try:
            # Try to get version from package
            sys.path.insert(0, str(self.src_dir))
            from aether_frame import __version__
            print(f"Current version: {__version__}")
            return 0
        except ImportError:
            # Fallback to pyproject.toml
            try:
                import tomllib
                with open(self.project_root / "pyproject.toml", "rb") as f:
                    data = tomllib.load(f)
                version = data.get("project", {}).get("version", "unknown")
                print(f"Current version: {version}")
                return 0
            except Exception as e:
                print(f"Error reading version: {e}")
                return 1


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Development tools for Aether Frame",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "command",
        nargs="?",
        default="help",
        help="Command to run (default: help)"
    )
    
    args = parser.parse_args()
    
    dev_tools = DevTools()
    
    # Get the method to call
    command = args.command.replace("-", "_")
    if not hasattr(dev_tools, command):
        print(f"Unknown command: {args.command}")
        dev_tools.help()
        return 1
        
    method = getattr(dev_tools, command)
    
    try:
        exit_code = method()
        sys.exit(exit_code or 0)
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()