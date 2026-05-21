# -*- coding: utf-8 -*-
from langchain_openai import ChatOpenAI
from config import settings


def get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        api_key=settings.DEEPSEEK_API_KEY,
        base_url=settings.DEEPSEEK_BASE_URL,
        model=settings.DEEPSEEK_MODEL_NAME,
        temperature=0.1,
        timeout=settings.LLM_TIMEOUT,
    )
