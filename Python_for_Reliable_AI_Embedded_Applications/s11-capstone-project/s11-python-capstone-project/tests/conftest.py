

import sys
import os
import pytest
from fastapi.testclient import TestClient

# Add project root to Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)