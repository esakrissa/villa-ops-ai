"""Per-model request options shared by the agent and title generation."""


def llm_extra_kwargs(model_id: str) -> dict:
    """Extra LiteLLM kwargs for ``model_id`` (passed via ChatLiteLLM ``model_kwargs``).

    OpenRouter: route each request to the provider with the lowest latency
    right now, instead of the default price-weighted load balancing.
    """
    if model_id.startswith("openrouter/"):
        return {"extra_body": {"provider": {"sort": "latency"}}}
    return {}
