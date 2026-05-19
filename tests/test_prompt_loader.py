from __future__ import annotations

from app.utils.prompt_loader import load_prompt


class TestPromptLoader:
    def test_load_outline_template(self):
        result = load_prompt("script_outline.j2", news_json='[{"index": 0, "title": "Test"}]')
        assert "Test" in result
        assert "AI前沿速递" in result
        assert "主持人" in result
        assert "技术专家" in result
        assert "segments" in result

    def test_load_dialogue_template(self):
        result = load_prompt(
            "script_dialogue.j2",
            outline_json='{"segments": []}',
            news_json='[{"index": 0, "title": "Test", "source": "TestSrc", "score": 8}]',
            rag_context="",
        )
        assert "主持人" in result
        assert "技术专家" in result
        assert "Test" in result
        assert "dialogue" in result

    def test_template_variable_substitution(self):
        result = load_prompt("script_outline.j2", news_json="MY_NEWS_DATA")
        assert "MY_NEWS_DATA" in result
        assert "{{" not in result
