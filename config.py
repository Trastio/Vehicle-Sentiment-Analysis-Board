# -*- coding: utf-8 -*-
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
from pathlib import Path


PROJECT_ROOT: Path = Path(__file__).resolve().parent
ENV_FILE: str = str(PROJECT_ROOT / ".env")


class Settings(BaseSettings):
    HOST: str = Field("0.0.0.0", description="Flask主机地址")
    PORT: int = Field(5000, description="Flask端口")
    DEBUG: bool = Field(True, description="调试模式")

    DEEPSEEK_API_KEY: Optional[str] = Field(None, description="DeepSeek API密钥")
    DEEPSEEK_BASE_URL: str = Field("https://api.deepseek.com", description="DeepSeek API基础URL")
    DEEPSEEK_MODEL_NAME: str = Field("deepseek-v4-pro", description="DeepSeek模型名称")

    TAVILY_API_KEY: Optional[str] = Field(None, description="Tavily API密钥")

    BOCHA_API_KEY: Optional[str] = Field(None, description="Bocha API密钥")
    BOCHA_BASE_URL: str = Field("https://api.bochaai.com/v1/ai-search", description="Bocha搜索URL")

    ANSPIRE_API_KEY: Optional[str] = Field(None, description="Anspire API密钥")
    ANSPIRE_BASE_URL: str = Field("https://plugin.anspire.cn/api/ntsearch/search", description="Anspire搜索URL")

    SEARCH_TOOL_TYPE: str = Field("tavily", description="搜索工具类型: tavily/bocha/anspire")

    DB_PATH: str = Field(str(PROJECT_ROOT / "data" / "autopulse.db"), description="SQLite数据库路径")
    LOG_DIR: str = Field(str(PROJECT_ROOT / "logs"), description="日志目录")

    RECURSION_LIMIT: int = Field(15, description="LangGraph递归限制")
    NODE_TIMEOUT: int = Field(30, description="节点超时秒数")
    LLM_TIMEOUT: int = Field(60, description="LLM调用超时秒数")
    MAX_API_CALLS: int = Field(5, description="单次查询最大API调用次数")
    MAX_CRAWLER_RESULTS: int = Field(200, description="爬虫单次最大返回记录数")
    FACT_CHECK_MAX_RETRIES: int = Field(2, description="事实校验最大重试次数")

    class Config:
        env_file = ENV_FILE
        env_prefix = ""
        case_sensitive = False
        extra = "allow"


settings = Settings()


def reload_settings():
    global settings
    settings = Settings()
