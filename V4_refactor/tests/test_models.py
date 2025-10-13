"""Unit tests for Pydantic models."""

import pytest
from pydantic import ValidationError
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src'))

from microtutor.models.requests import (
    StartCaseRequest,
    ChatRequest,
    FeedbackRequest,
    Message
)


def test_message_valid():
    """Test valid Message model."""
    msg = Message(role="user", content="Hello")
    assert msg.role == "user"
    assert msg.content == "Hello"


def test_message_invalid_role():
    """Test Message with invalid role."""
    with pytest.raises(ValidationError):
        Message(role="invalid", content="Hello")


def test_start_case_request_valid():
    """Test valid StartCaseRequest."""
    request = StartCaseRequest(
        organism="staphylococcus aureus",
        case_id="test_123"
    )
    assert request.organism == "staphylococcus aureus"
    assert request.case_id == "test_123"
    assert request.model_name == "o3-mini"  # Default


def test_start_case_request_empty_organism():
    """Test StartCaseRequest with empty organism."""
    with pytest.raises(ValidationError):
        StartCaseRequest(
            organism="",
            case_id="test_123"
        )


def test_start_case_request_missing_case_id():
    """Test StartCaseRequest with missing case_id."""
    with pytest.raises(ValidationError):
        StartCaseRequest(organism="staphylococcus aureus")


def test_chat_request_valid():
    """Test valid ChatRequest."""
    request = ChatRequest(
        message="What are the symptoms?",
        history=[],
        case_id="test_123",
        organism_key="staphylococcus aureus"
    )
    assert request.message == "What are the symptoms?"
    assert request.case_id == "test_123"


def test_chat_request_empty_message():
    """Test ChatRequest with empty message."""
    with pytest.raises(ValidationError):
        ChatRequest(
            message="",
            history=[]
        )


def test_chat_request_whitespace_message():
    """Test ChatRequest with whitespace-only message."""
    with pytest.raises(ValidationError):
        ChatRequest(
            message="   ",
            history=[]
        )


def test_feedback_request_valid():
    """Test valid FeedbackRequest."""
    request = FeedbackRequest(
        rating=4,
        message="Test message",
        history=[]
    )
    assert request.rating == 4
    assert request.message == "Test message"


def test_feedback_request_invalid_rating_low():
    """Test FeedbackRequest with rating too low."""
    with pytest.raises(ValidationError):
        FeedbackRequest(
            rating=0,
            message="Test",
            history=[]
        )


def test_feedback_request_invalid_rating_high():
    """Test FeedbackRequest with rating too high."""
    with pytest.raises(ValidationError):
        FeedbackRequest(
            rating=6,
            message="Test",
            history=[]
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

