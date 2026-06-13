"""Tests for the shared JSON parser (utils/json_parser.py)."""
import pytest
import json

from utils.json_parser import parse_llm_json


# ── conversation_agent.parse_llm_json ───────────────────────────────────

class TestParseLlmJsonBasic:
    def test_clean_json(self):
        raw = '{"project_name": "Test", "sections": {}}'
        result = parse_llm_json(raw)
        assert result["project_name"] == "Test"

    def test_markdown_fenced_json(self):
        raw = '```json\n{"project_name": "Test", "sections": {}}\n```'
        result = parse_llm_json(raw)
        assert result["project_name"] == "Test"

    def test_trailing_comma(self):
        raw = '{"project_name": "Test", "sections": {},}'
        result = parse_llm_json(raw)
        assert result["project_name"] == "Test"

    def test_js_style_comments(self):
        raw = '{"project_name": "Test" // a comment\n, "sections": {}}'
        result = parse_llm_json(raw)
        assert result["project_name"] == "Test"

    def test_invalid_escape_sequences(self):
        raw = '{"project_name": "\\existing system", "sections": {}}'
        result = parse_llm_json(raw)
        assert result["project_name"] == "existing system"

    def test_no_json_raises(self):
        with pytest.raises(ValueError, match="No JSON"):
            parse_llm_json("Here is some plain text with no JSON at all.")

    def test_nested_sections(self):
        data = {
            "project_name": "Demo",
            "sections": {
                "executive_summary": {
                    "content": "Summary text",
                    "is_ai_assumed": False,
                },
                "business_background": {
                    "content": "Background text",
                    "is_ai_assumed": True,
                },
            },
        }
        raw = json.dumps(data)
        result = parse_llm_json(raw)
        assert len(result["sections"]) == 2
        assert result["sections"]["executive_summary"]["is_ai_assumed"] is False

    def test_prose_before_json(self):
        raw = 'Here is the BRD:\n\n{"project_name": "Test", "sections": {}}'
        result = parse_llm_json(raw)
        assert result["project_name"] == "Test"


# ── brd_update_agent.parse_llm_json ───────────────────────────────

class TestParseLlmJsonUpdate:
    def test_clean_json(self):
        raw = '{"found": true, "page_id": "123", "title": "Test"}'
        result = parse_llm_json(raw)
        assert result["found"] is True

    def test_markdown_fenced(self):
        raw = '```json\n{"found": true, "page_id": "123"}\n```'
        result = parse_llm_json(raw)
        assert result["page_id"] == "123"

    def test_trailing_comma(self):
        raw = '{"match": true, "summary": "Updated",}'
        result = parse_llm_json(raw)
        assert result["match"] is True

    def test_no_json_raises(self):
        with pytest.raises(ValueError, match="No JSON"):
            parse_llm_json("No valid JSON here.")

    def test_update_result(self):
        raw = json.dumps({
            "match": True,
            "no_changes": False,
            "summary": "Updated section 3",
            "sections_updated": ["Business Objectives"],
            "published": True,
            "new_version": 5,
        })
        result = parse_llm_json(raw)
        assert result["published"] is True
        assert result["new_version"] == 5
