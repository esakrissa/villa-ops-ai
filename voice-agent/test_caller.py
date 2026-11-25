"""Typed test call: log in, get a voice session from the backend, join, type questions.

The agent reads LiveKit's ``lk.chat`` text stream like speech and answers in voice, so this checks
the whole path (backend token → dispatch → tools → transcript) without a microphone. Per turn it
prints the time to the agent's first words (transcription stream) and every tool event.

    uv run python test_caller.py --email demo@villaops.ai --password demo1234 \
        "Find me some good restaurants in Ubud" "What's our cancellation policy?"
"""

import argparse
import asyncio
import json
import sys
import time

import httpx
from livekit import rtc

CHAT_TOPIC = "lk.chat"
TOOL_TOPIC = "villa.tool"


class Caller:
    def __init__(self) -> None:
        self.room = rtc.Room()
        self.state = "initializing"
        self.state_changed = asyncio.Event()
        self.agent_text: list[str] = []
        self.first_words_at: float | None = None
        self.first_speaking_at: float | None = None
        self.tools: list[dict] = []
        self.tasks: set[asyncio.Task] = set()

    def spawn(self, coro) -> None:
        t = asyncio.create_task(coro)
        self.tasks.add(t)
        t.add_done_callback(self.tasks.discard)

    async def join(self, url: str, token: str) -> None:
        @self.room.on("participant_attributes_changed")
        def _attrs(changed: dict, p: rtc.Participant) -> None:
            if "lk.agent.state" in changed:
                self.state = changed["lk.agent.state"]
                if self.state == "speaking" and self.first_speaking_at is None:
                    self.first_speaking_at = time.perf_counter()
                self.state_changed.set()

        @self.room.on("participant_connected")
        def _joined(p: rtc.RemoteParticipant) -> None:
            if "lk.agent.state" in p.attributes:
                self.state = p.attributes["lk.agent.state"]
                self.state_changed.set()

        self.room.register_text_stream_handler("lk.transcription", lambda r, _i: self.spawn(self.on_text(r)))
        self.room.register_text_stream_handler(TOOL_TOPIC, lambda r, _i: self.spawn(self.on_tool(r)))
        await self.room.connect(url, token)

    async def on_text(self, reader: rtc.TextStreamReader) -> None:
        chunks = []
        async for chunk in reader:
            if self.first_words_at is None and chunk.strip():
                self.first_words_at = time.perf_counter()
            chunks.append(chunk)
        text = "".join(chunks).strip()
        if text:
            self.agent_text.append(text)

    async def on_tool(self, reader: rtc.TextStreamReader) -> None:
        ev = json.loads(await reader.read_all())
        self.tools.append(ev)
        extra = f" {ev.get('seconds', '')}s" if ev["status"] != "running" else ""
        detail = ev.get("error") or (ev.get("result", "")[:100] if ev["status"] == "ok" else json.dumps(ev["args"]))
        print(f"    [tool] {ev['name']} {ev['status']}{extra} {detail}")

    async def wait_state(self, want: str, limit_s: float) -> None:
        async with asyncio.timeout(limit_s):
            while self.state != want:
                self.state_changed.clear()
                await self.state_changed.wait()

    async def until_quiet(self, limit_s: float, quiet_s: float = 8.0) -> None:
        """The agent spoke and then kept listening for quiet_s (tool turns speak, think, speak)."""
        await self.wait_state("speaking", limit_s)
        async with asyncio.timeout(limit_s):
            while True:
                await self.wait_state("listening", limit_s)
                self.state_changed.clear()
                try:
                    await asyncio.wait_for(self.state_changed.wait(), quiet_s)
                except TimeoutError:
                    return

    async def ask(self, prompt: str, limit_s: float) -> None:
        await self.wait_state("listening", limit_s)
        self.agent_text.clear()
        self.first_words_at = None
        self.first_speaking_at = None
        print(f"\n> {prompt}")
        sent = time.perf_counter()
        await self.room.local_participant.send_text(prompt, topic=CHAT_TOPIC)
        try:
            await self.until_quiet(limit_s)
        except TimeoutError:
            print("  !! timed out")
        await asyncio.sleep(0.5)
        speak = f"{self.first_speaking_at - sent:.2f}s" if self.first_speaking_at else "-"
        words = sum(len(t.split()) for t in self.agent_text)
        print(f"  agent speaking after {speak}, {words} words, total {time.perf_counter() - sent:.1f}s")
        print("  Villa:", " | ".join(self.agent_text))


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("prompts", nargs="*")
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--email", default="demo@villaops.ai")
    ap.add_argument("--password", default="demo1234")
    ap.add_argument("--model", default=None)
    ap.add_argument("--conversation", default=None)
    ap.add_argument("--timeout", type=float, default=90)
    a = ap.parse_args()

    async with httpx.AsyncClient(base_url=a.api, timeout=20) as http:
        r = await http.post("/api/v1/auth/login", json={"email": a.email, "password": a.password})
        r.raise_for_status()
        token = r.json()["tokens"]["access_token"]
        body = {"model": a.model, "conversation_id": a.conversation}
        r = await http.post("/api/v1/voice/session", json=body, headers={"Authorization": f"Bearer {token}"})
        r.raise_for_status()
        sess = r.json()
    print(f"room {sess['room_name']} conversation {sess['conversation_id']} model {sess['model']}")

    caller = Caller()
    t0 = time.perf_counter()
    await caller.join(sess["server_url"], sess["participant_token"])
    try:
        joined = time.perf_counter()
        await caller.until_quiet(a.timeout, quiet_s=2.5)
        speak = caller.first_speaking_at - joined if caller.first_speaking_at else -1
        said = " | ".join(caller.agent_text)
        print(f"joined in {joined - t0:.1f}s, greeting started {speak:.1f}s after joining: {said}")
        for p in a.prompts:
            await caller.ask(p, a.timeout)
    finally:
        await caller.room.disconnect()
    print(f"\nconversation_id={sess['conversation_id']}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
