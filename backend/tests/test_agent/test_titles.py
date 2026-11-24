"""Tests for LLM-generated conversation titles."""

import asyncio
import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.titles import MAX_TITLE_LENGTH, clean_title, generate_llm_title
from app.api.v1.chat import _apply_generated_title


def _completion(text: str):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


class TestCleanTitle:
    def test_plain_title(self):
        assert clean_title("Weekly arrivals overview") == "Weekly arrivals overview"

    def test_strips_quotes_prefix_and_punctuation(self):
        assert clean_title('Title: "Occupancy for November."') == "Occupancy for November"

    def test_uses_first_line_only(self):
        assert clean_title("Guest lookup\nHere is why I chose it") == "Guest lookup"

    def test_collapses_whitespace(self):
        assert clean_title("  Late   check-out   request ") == "Late check-out request"

    def test_empty_returns_none(self):
        assert clean_title("   ") is None
        assert clean_title('""') is None

    def test_truncates_at_word_boundary(self):
        title = clean_title("word " * 30)
        assert title is not None
        assert len(title) <= MAX_TITLE_LENGTH
        assert not title.endswith(" ")


@pytest.mark.asyncio
class TestGenerateLlmTitle:
    async def test_returns_cleaned_title(self):
        with patch("app.agent.titles.litellm.acompletion", AsyncMock(return_value=_completion('"Upcoming arrivals."'))):
            assert await generate_llm_title("Who is arriving this week?") == "Upcoming arrivals"

    async def test_falls_back_to_next_model(self):
        mock = AsyncMock(side_effect=[RuntimeError("503 high demand"), _completion("Occupancy check")])
        with (
            patch("app.agent.titles.settings.title_llm_model", "gemini/title-model"),
            patch("app.agent.titles.settings.default_llm_model", "gemini/default-model"),
            patch("app.agent.titles.litellm.acompletion", mock),
        ):
            assert await generate_llm_title("What's my occupancy?") == "Occupancy check"
        assert [c.kwargs["model"] for c in mock.call_args_list] == ["gemini/title-model", "gemini/default-model"]

    async def test_returns_none_when_all_models_fail(self):
        with patch("app.agent.titles.litellm.acompletion", AsyncMock(side_effect=RuntimeError("down"))):
            assert await generate_llm_title("Hello") is None


@pytest.mark.asyncio
class TestApplyGeneratedTitle:
    async def test_saves_title_and_returns_event(self):
        session = MagicMock()
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        factory = MagicMock()
        factory.return_value.__aenter__ = AsyncMock(return_value=session)
        factory.return_value.__aexit__ = AsyncMock(return_value=False)

        conv_id = uuid.uuid4()
        task = asyncio.create_task(asyncio.sleep(0, result="Upcoming arrivals"))
        with patch("app.api.v1.chat.async_session_factory", factory):
            event = await _apply_generated_title(task, conv_id)

        assert json.loads(event) == {"type": "title", "conversation_id": str(conv_id), "title": "Upcoming arrivals"}
        session.execute.assert_awaited_once()
        session.commit.assert_awaited_once()

    async def test_no_event_when_generation_failed(self):
        task = asyncio.create_task(asyncio.sleep(0, result=None))
        assert await _apply_generated_title(task, uuid.uuid4()) is None

    async def test_no_event_when_task_raises(self):
        async def boom():
            raise RuntimeError("provider error")

        task = asyncio.create_task(boom())
        assert await _apply_generated_title(task, uuid.uuid4()) is None
