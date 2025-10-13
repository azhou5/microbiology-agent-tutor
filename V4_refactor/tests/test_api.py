"""Integration tests for API endpoints."""

import pytest
from fastapi.testclient import TestClient
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src'))

from microtutor.api.app import app

client = TestClient(app)


def test_root():
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "MicroTutor API"
    assert data["version"] == "4.0.0"


def test_health_check():
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_api_info():
    """Test API info endpoint."""
    response = client.get("/api/v1/info")
    assert response.status_code == 200
    data = response.json()
    assert "endpoints" in data


def test_start_case_missing_organism():
    """Test start_case with missing organism."""
    response = client.post(
        "/api/v1/start_case",
        json={"case_id": "test_123"}
    )
    assert response.status_code == 422  # Validation error


def test_start_case_empty_organism():
    """Test start_case with empty organism."""
    response = client.post(
        "/api/v1/start_case",
        json={"organism": "", "case_id": "test_123"}
    )
    assert response.status_code == 422  # Validation error


def test_chat_without_case_id():
    """Test chat without case_id."""
    response = client.post(
        "/api/v1/chat",
        json={
            "message": "Hello",
            "history": []
        }
    )
    assert response.status_code == 400


def test_chat_without_organism():
    """Test chat without organism_key."""
    response = client.post(
        "/api/v1/chat",
        json={
            "message": "Hello",
            "history": [],
            "case_id": "test_123"
        }
    )
    assert response.status_code == 400


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

