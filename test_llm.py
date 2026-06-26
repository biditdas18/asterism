import os
import pytest
import db
from db import init_db, add_edge, get_edges
from context import serialize_graph
from llm import query, _parse_traversals

db.DB_PATH = os.path.join(os.path.dirname(__file__), "test_asterism.db")

def setup_function():
    if os.path.exists(db.DB_PATH):
        os.remove(db.DB_PATH)
    init_db()

def teardown_function():
    if os.path.exists(db.DB_PATH):
        os.remove(db.DB_PATH)

def test_serialize_graph_empty():
    result = serialize_graph()
    assert "Knowledge Graph State" in result
    assert "Nodes" in result
    assert "Edges" in result

def test_serialize_graph_with_data():
    add_edge("Bidit", "Python")
    add_edge("Python", "Machine Learning")
    result = serialize_graph()
    assert "Bidit" in result
    assert "Python" in result
    assert "Machine Learning" in result

def test_parse_traversals():
    text = """
    Let me reason through this.
    TRAVERSAL: Python -> Machine Learning
    TRAVERSAL: Machine Learning -> Neural Networks
    """
    result = _parse_traversals(text)
    assert ("Python", "Machine Learning") in result
    assert ("Machine Learning", "Neural Networks") in result

def test_parse_traversals_chained():
    text = "TRAVERSAL: Bidit -> Python -> Machine Learning -> Neural Networks\n"
    result = _parse_traversals(text)
    assert result == [
        ("Bidit", "Python"),
        ("Python", "Machine Learning"),
        ("Machine Learning", "Neural Networks"),
    ]

def test_parse_traversals_empty():
    result = _parse_traversals("No traversals here.")
    assert result == []

def test_live_query_returns_response():
    """Live API call — requires ANTHROPIC_API_KEY in environment."""
    add_edge("Bidit", "Python")
    add_edge("Python", "Machine Learning")
    result = query("What does Bidit know about Machine Learning?")
    assert "response" in result
    assert isinstance(result["response"], str)
    assert len(result["response"]) > 0
    assert "tokens_used" in result
