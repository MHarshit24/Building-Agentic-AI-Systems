"""
Pytest Configuration
Shared fixtures and test configuration.
"""

import pytest
import os
from pathlib import Path

# Set test environment variables
os.environ.setdefault("DB_TABLE_NAME", "test_diet_counselling_vector_store")
os.environ.setdefault("API_HOST", "0.0.0.0")
os.environ.setdefault("API_PORT", "8000")

@pytest.fixture
def project_root():
    """Get the project root directory."""
    return Path(__file__).parent.parent

@pytest.fixture
def documents_dir(project_root):
    """Get the Documents directory path."""
    return project_root / "Documents"

