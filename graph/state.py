# -*- coding: utf-8 -*-
from typing import TypedDict, List, Dict, Any


class AutoPulseState(TypedDict, total=False):
    user_input: str
    car_model: str
    keywords: List[str]
    intent: str
    focus_dimensions: List[str]
    search_strategy: Dict[str, Any]
    selected_sources: List[str]
    skipped_sources: List[str]
    api_raw_data: List[Dict[str, Any]]
    crawler_raw_data: List[Dict[str, Any]]
    merged_data: List[Dict[str, Any]]
    sentiment_results: List[Dict[str, Any]]
    hotspot_keywords: List[Dict[str, Any]]
    major_opinions: List[Dict[str, Any]]
    alert_level: str
    volume_stats: Dict[str, Any]
    fact_check_passed: bool
    fact_check_errors: List[str]
    quality_score: float
    llm_suggestions: List[str]
    insight_report: Dict[str, Any]
    agent_response: Dict[str, Any]
    dashboard_data: Dict[str, Any]
    iteration_count: int
    error_messages: List[str]
    progress: int
    current_node: str
