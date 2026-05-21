# -*- coding: utf-8 -*-
from typing import Dict, Any, List, Optional
from db.conversation_db import get_recent_messages, update_conversation
from config import settings


class ContextManager:
    def __init__(self, max_context_messages: int = 20):
        self.max_context_messages = max_context_messages
        self._cache: Dict[str, Dict[str, Any]] = {}

    def load_context(self, conversation_id: str) -> Dict[str, Any]:
        if conversation_id in self._cache:
            return self._cache[conversation_id]

        messages = get_recent_messages(conversation_id, self.max_context_messages)
        context_msgs = []
        for msg in messages:
            context_msgs.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", ""),
                "message_type": msg.get("message_type", "text"),
                "car_model": "",
            })

        car_model = ""
        for msg in reversed(context_msgs):
            if msg["role"] == "user" and msg["content"]:
                from agent.intent_recognizer import _extract_car_model
                extracted = _extract_car_model(msg["content"])
                if extracted:
                    car_model = extracted
                    break

        context = {
            "conversation_id": conversation_id,
            "messages": context_msgs,
            "car_model": car_model,
            "has_analysis": any(msg["message_type"] in ("visual_report", "opinion_report") for msg in context_msgs),
        }

        self._cache[conversation_id] = context
        return context

    def update_car_model(self, conversation_id: str, car_model: str):
        if conversation_id in self._cache:
            self._cache[conversation_id]["car_model"] = car_model
        update_conversation(conversation_id, car_model=car_model)

    def get_car_model(self, conversation_id: str) -> str:
        context = self.load_context(conversation_id)
        return context.get("car_model", "")

    def get_messages_for_llm(self, conversation_id: str) -> List[Dict[str, str]]:
        context = self.load_context(conversation_id)
        result = []
        for msg in context.get("messages", []):
            if msg["message_type"] == "text":
                result.append({"role": msg["role"], "content": msg["content"]})
        return result[-self.max_context_messages:]

    def invalidate(self, conversation_id: str):
        if conversation_id in self._cache:
            del self._cache[conversation_id]
