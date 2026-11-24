"""LLM-generated conversation titles.

New conversations start with a truncated-message title (see
``memory.generate_title``) so they appear in the sidebar immediately. In
parallel, a small fast model writes a short descriptive title which replaces
it once ready. Title calls are not recorded as LLMUsage, so they don't count
against the user's AI query limit.
"""

import asyncio
import logging
import re

import litellm

from app.agent.llm_options import llm_extra_kwargs
from app.config import settings

logger = logging.getLogger(__name__)

TITLE_TIMEOUT_SECONDS = 10
MAX_TITLE_LENGTH = 60

TITLE_PROMPT = (
    "Write a short title (3 to 6 words) for a conversation that starts with the "
    "message below. The user is a villa property manager in Bali talking to an "
    "operations assistant. Use sentence case, no quotes, no emoji, no trailing "
    "punctuation. Reply with the title only.\n\nMessage: {message}"
)


def clean_title(raw: str) -> str | None:
    """Normalise model output into a sidebar-friendly title."""
    title = raw.strip().splitlines()[0] if raw.strip() else ""
    title = re.sub(r"^(title\s*:\s*)", "", title, flags=re.IGNORECASE)
    title = title.strip(" \"'`*#").rstrip(".!?:;,")
    title = re.sub(r"\s+", " ", title)
    if not title:
        return None
    if len(title) > MAX_TITLE_LENGTH:
        title = title[:MAX_TITLE_LENGTH].rsplit(" ", 1)[0]
    return title


async def generate_llm_title(message: str) -> str | None:
    """Ask the title model (then the default model) for a title.

    Returns None if every model fails or times out — callers keep the
    truncated fallback title in that case.
    """
    prompt = TITLE_PROMPT.format(message=message.strip()[:1000])
    models = list(dict.fromkeys([settings.title_llm_model, settings.default_llm_model]))

    for model in models:
        try:
            response = await asyncio.wait_for(
                litellm.acompletion(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=256,
                    temperature=1.0,
                    **llm_extra_kwargs(model),
                ),
                timeout=TITLE_TIMEOUT_SECONDS,
            )
            title = clean_title(response.choices[0].message.content or "")
            if title:
                return title
        except Exception as exc:
            logger.warning("Title generation with %s failed: %r", model, exc)
    return None
