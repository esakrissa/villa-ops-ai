"""The speech, language and voice models, each with a backup from another vendor.

- LLM: the model picked in the UI via OpenRouter (default Claude Haiku 5.5, benchmarked fastest
  for its price on the real tool set), then Gemini 3.1 Flash-Lite via OpenRouter, then GPT-4.1 mini
  on LiveKit Inference, which doesn't depend on OpenRouter at all. A model that stays silent past
  the attempt timeout loses the turn to the next one.
- Voice: ElevenLabs Flash v2.5 (your ElevenLabs key), then the LiveKit Inference voices that
  mini-kulu uses: Fish Audio S2.1 Pro, then Cartesia Sonic-3. A bad key, an exhausted free tier or
  an outage costs one sentence, not the call.
- STT and turn detection run on LiveKit Inference (AssemblyAI Universal-3.6 Pro, LiveKit's v1
  end-of-turn model), like mini-kulu.
"""

import logging

from livekit.agents import APIConnectOptions, inference, llm, tts
from livekit.plugins import elevenlabs, openai

from villa.settings import Settings

logger = logging.getLogger("villa.models")

OPENROUTER_URL = "https://openrouter.ai/api/v1"
FISH_VOICE = ("fishaudio/s2.1-pro", "fa4c9eb3dccc4806b382b40d61c6b10a")
CARTESIA_VOICE = ("cartesia/sonic-3", "9626c31c-bec5-4cca-baa8-f8ba9e84c8bc")
STT_MODEL = "assemblyai/universal-3-6-pro"

# One pass through each chain per turn: the session defaults (3 retries, 2 s apart) would keep
# the caller waiting long before a backup speaks.
LLM_CONN_OPTIONS = APIConnectOptions(max_retry=0)


def tts_conn_options(timeout_s: float) -> APIConnectOptions:
    return APIConnectOptions(max_retry=0, timeout=timeout_s)


def openrouter_llm(model: str, api_key: str) -> llm.LLM:
    extra: dict = {"provider": {"sort": "latency"}}
    if model.startswith("openai/gpt-6") or model.startswith("openai/gpt-5"):
        # Voice needs the first token fast; these reason by default
        extra["reasoning"] = {"effort": "low"}
    return openai.LLM(
        model=model,
        base_url=OPENROUTER_URL,
        api_key=api_key,
        temperature=0.7,
        max_completion_tokens=4000,  # a 7-day itinerary tool call is ~1.5-1.8k tokens
        extra_body=extra,
        extra_headers={"X-Title": "VillaOps AI - Villa voice"},
        _strict_tool_schema=False,  # MCP schemas have optional fields
    )


def llm_chain(s: Settings, model: str) -> llm.FallbackAdapter:
    models = [model] + [m for m in (s.backup_model,) if m != model]
    chain: list[llm.LLM] = [openrouter_llm(m, s.openrouter_api_key) for m in models]
    chain.append(inference.LLM(model=s.inference_backup_model))
    logger.info("LLM chain: %s + inference %s", models, s.inference_backup_model)
    # The attempt timeout must cover a whole tool-call generation: the OpenAI plugin hands a tool
    # call over only once its arguments are complete, and a 7-day itinerary takes ~7 s (Haiku 5.5).
    adapter = llm.FallbackAdapter(chain, attempt_timeout=s.llm_timeout_s, max_retry_per_llm=0)

    @adapter.on("llm_availability_changed")
    def _changed(ev: llm.AvailabilityChangedEvent) -> None:
        logger.warning("LLM %s is %s", ev.llm.model, "back" if ev.available else "unavailable, falling back")

    return adapter


def tts_chain(s: Settings) -> tts.FallbackAdapter:
    voices: list[tts.TTS] = []
    if s.eleven_api_key:
        voices.append(
            elevenlabs.TTS(
                api_key=s.eleven_api_key,
                model=s.eleven_model,
                voice_id=s.eleven_voice_id,
            )
        )
    else:
        logger.warning("ELEVEN_API_KEY is empty: speaking with the LiveKit Inference voices")
    voices.append(inference.TTS(model=FISH_VOICE[0], voice=FISH_VOICE[1]))
    voices.append(inference.TTS(model=CARTESIA_VOICE[0], voice=CARTESIA_VOICE[1]))
    chain = ([f"elevenlabs/{s.eleven_model} (voice {s.eleven_voice_id})"] if s.eleven_api_key else []) + [
        f"{FISH_VOICE[0]} (inference)",
        f"{CARTESIA_VOICE[0]} (inference)",
    ]
    logger.info("TTS chain: %s; STT: %s", " → ".join(chain), STT_MODEL)
    adapter = tts.FallbackAdapter(voices, max_retry_per_tts=0)

    @adapter.on("tts_availability_changed")
    def _changed(ev: tts.AvailabilityChangedEvent) -> None:
        logger.warning("TTS %s is %s", ev.tts.label, "back" if ev.available else "unavailable, falling back")

    return adapter


def stt() -> inference.STT:
    return inference.STT(model=STT_MODEL, language="en")
