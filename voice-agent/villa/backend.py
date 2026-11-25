"""The VillaOps backend, from the agent's side: earlier turns in, transcript turns out.

Turns are saved in order by one background worker, so a slow request never delays the voice
pipeline, and a backend hiccup costs at most a few transcript lines (retried once).
"""

import asyncio
import contextlib
import logging
from typing import Any

import httpx

logger = logging.getLogger("villa.backend")

HEADER = "X-Voice-Agent-Key"


class Backend:
    def __init__(self, base_url: str, secret: str, user_id: str, conversation_id: str, model: str) -> None:
        self._client = httpx.AsyncClient(base_url=base_url, headers={HEADER: secret}, timeout=10)
        self._user_id = user_id
        self._conversation_id = conversation_id
        self._model = model
        self._queue: asyncio.Queue[list[dict[str, Any]] | None] = asyncio.Queue()
        self._worker = asyncio.create_task(self._run(), name="villa-transcript")
        # A new conversation is created by its first saved turn. Villa's greeting waits for the
        # caller's first words, so a call nobody speaks in leaves no empty chat in the history.
        self._held: list[dict[str, Any]] | None = []

    async def history(self) -> tuple[str | None, list[dict[str, str]]]:
        """Title and the last turns of the conversation (empty for a new one)."""
        try:
            r = await self._client.get(
                f"/api/v1/voice/internal/conversations/{self._conversation_id}",
                params={"user_id": self._user_id},
            )
            r.raise_for_status()
            data = r.json()
            messages = data.get("messages") or []
            if messages:
                self._release()  # an existing conversation: save turns as they come
            return data.get("title"), messages
        except Exception as e:
            logger.warning("couldn't load conversation history: %r", e)
            return None, []

    # ---- transcript -------------------------------------------------------------------

    def user(self, text: str) -> None:
        self._release()
        self._put([{"role": "user", "content": text, "model_used": self._model}])

    def assistant(self, text: str) -> None:
        self._put([{"role": "assistant", "content": text, "model_used": self._model}])

    def tool_step(self, calls: list[dict[str, Any]], results: list[tuple[str, str]]) -> None:
        """One assistant step that called tools, then each tool's result (call id, text)."""
        batch: list[dict[str, Any]] = [
            {"role": "assistant", "content": "", "tool_calls": calls, "model_used": self._model}
        ]
        batch += [{"role": "tool", "content": text, "tool_call_id": cid} for cid, text in results]
        self._put(batch)

    def _release(self) -> None:
        held, self._held = self._held, None
        if held:
            self._queue.put_nowait(held)

    def _put(self, messages: list[dict[str, Any]]) -> None:
        if self._held is not None:
            self._held.extend(messages)
        else:
            self._queue.put_nowait(messages)

    async def _run(self) -> None:
        while (batch := await self._queue.get()) is not None:
            body = {"user_id": self._user_id, "conversation_id": self._conversation_id, "messages": batch}
            for attempt in (1, 2):
                try:
                    r = await self._client.post("/api/v1/voice/internal/messages", json=body)
                    r.raise_for_status()
                    break
                except Exception as e:
                    logger.warning("saving transcript failed (attempt %d): %r", attempt, e)
                    await asyncio.sleep(0.5)

    async def aclose(self) -> None:
        """Flush what's queued (bounded), then close."""
        self._queue.put_nowait(None)
        with contextlib.suppress(TimeoutError, asyncio.CancelledError):
            await asyncio.wait_for(self._worker, timeout=8)
        await self._client.aclose()
