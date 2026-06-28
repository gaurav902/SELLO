"""
SELLO — Backend API Tests
"""

from fastapi.testclient import TestClient
import sys
import os

# Adjust path to import backend modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../backend")))

from main import app

client = TestClient(app)


def test_health_check():
    """Verify that the health check endpoint returns 200 and expected status."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "app" in data
    assert "version" in data
