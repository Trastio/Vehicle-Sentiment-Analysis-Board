# -*- coding: utf-8 -*-
from agent.chat_agent import ChatAgent

_agent_instance = None


def get_agent() -> ChatAgent:
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = ChatAgent()
    return _agent_instance
