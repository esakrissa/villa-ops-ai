"""Agent state schema for the LangGraph graph."""

import operator
from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage


class AgentState(TypedDict):
    """State for the VillaOps AI agent graph.

    The Annotated[..., operator.add] tells LangGraph to append new messages
    to the existing list rather than replacing it.
    """

    messages: Annotated[list[AnyMessage], operator.add]
