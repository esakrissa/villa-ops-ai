"""Agent state schema for the LangGraph graph."""

from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """State for the VillaOps AI agent graph.

    ``add_messages`` appends new messages, de-duplicates by id, and honours
    ``RemoveMessage(id=REMOVE_ALL_MESSAGES)`` — each chat run starts with that
    marker followed by the history loaded from Postgres, so the checkpointed
    thread is reset to the DB copy instead of growing a duplicate on every turn
    (with ``operator.add`` a 20-message chat had 47 messages in state).
    """

    messages: Annotated[list[AnyMessage], add_messages]
    user_id: str
