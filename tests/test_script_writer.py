from __future__ import annotations

from app.agents.script_writer.writer import (
    _generate_fallback,
    _build_rag_context,
    _fallback_dialogue_high,
    _fallback_dialogue_mid,
    _fallback_dialogue_low,
    _fallback_en_dialogue,
    HOST,
    EXPERT,
)


class TestFallbackScripts:
    def test_generate_fallback_creates_scripts(self):
        news_items = [
            {"title": "GPT-5发布", "source": "OpenAI", "importance_score": 9, "url": "https://example.com/1", "language": "zh"},
            {"title": "新AI芯片发布", "source": "NVIDIA", "importance_score": 6, "url": "https://example.com/2", "language": "zh"},
        ]
        scripts = _generate_fallback(news_items)
        assert len(scripts) == 2
        for s in scripts:
            assert "dialogue" in s
            assert "script" in s
            assert len(s["dialogue"]) > 0
            assert s["is_last"] is False

    def test_fallback_dialogue_has_two_speakers(self):
        news_items = [
            {"title": "Test News", "source": "TestSource", "importance_score": 8, "url": "https://example.com/1", "language": "zh"},
        ]
        scripts = _generate_fallback(news_items)
        dialogue = scripts[0]["dialogue"]
        speakers = {d["speaker"] for d in dialogue}
        assert HOST in speakers
        assert EXPERT in speakers

    def test_high_score_generates_more_dialogue(self):
        d_high = _fallback_dialogue_high("Test", "Src", 9, "")
        d_low = _fallback_dialogue_low("Test", "Src", 4, "")
        assert len(d_high) >= len(d_low)

    def test_en_fallback_generates_english(self):
        d = _fallback_en_dialogue("GPT-5 Released", "TechCrunch", 8, "")
        assert len(d) > 0
        # check English content
        assert any("GPT" in turn["text"] for turn in d)

    def test_rag_context_empty(self):
        result = _build_rag_context([])
        assert result == ""

    def test_rag_context_with_news(self):
        related = [{"title": "GPT-4发布", "source": "OpenAI", "importance_score": 8}]
        result = _build_rag_context(related)
        assert "GPT-4" in result
        assert "OpenAI" in result

    def test_transition_added_after_first_item(self):
        news_items = [
            {"title": "News A", "source": "S1", "importance_score": 7, "url": "u1", "language": "zh"},
            {"title": "News B", "source": "S2", "importance_score": 6, "url": "u2", "language": "zh"},
        ]
        scripts = _generate_fallback(news_items)
        assert len(scripts) == 2
        # First script should be is_first
        assert scripts[0]["is_first"] is True
        # Second script's first dialogue line should include a transition
        second_first_text = scripts[1]["dialogue"][0]["text"]
        assert len(second_first_text) > 20  # should have transition + content
