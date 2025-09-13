# -*- coding: utf-8 -*-
"""Pytest configuration for Aether Frame tests."""

import os
import sys

import pytest

# Add project root to Python path for all tests
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
src_path = os.path.join(project_root, "src")
sys.path.insert(0, src_path)


@pytest.fixture(scope="session")
def project_root():
    """Provide project root path to tests."""
    return project_root


@pytest.fixture(scope="session")
def src_path():
    """Provide source code path to tests."""
    return src_path


# Configure pytest to handle async tests
pytest_plugins = ["pytest_asyncio"]
