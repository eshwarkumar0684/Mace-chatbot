"""Tests for intent classification and routing."""

import pytest

from backend.agent.intent import classify_intent, route_for_intent


@pytest.mark.parametrize(
    "question,expected",
    [
        ("What courses does MACE AI Academy provide?", "course_inquiry"),
        ("What is AI & ML with Generative AI?", "course_inquiry"),
        ("What is the course duration?", "course_inquiry"),
        ("What are the fees?", "course_inquiry"),
        ("Tell me about AI & ML with Generative AI.", "course_inquiry"),
        ("Book a demo", "book_demo"),
        ("I want to join", "lead_capture"),
        ("Enroll me", "lead_capture"),
        ("Register me", "lead_capture"),
        ("I am interested in this course", "lead_capture"),
        ("Contact me", "lead_capture"),
        ("Hello", "general_chat"),
        ("Hi there", "general_chat"),
    ],
)
def test_keyword_intent_classification(question, expected):
    assert classify_intent(question, llm=None) == expected


@pytest.mark.parametrize(
    "intent,route",
    [
        ("course_inquiry", "rag_retrieval"),
        ("general_chat", "greeting_response"),
        ("book_demo", "demo_workflow"),
        ("lead_capture", "lead_workflow"),
    ],
)
def test_route_for_intent(intent, route):
    assert route_for_intent(intent) == route
