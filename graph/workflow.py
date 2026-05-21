# -*- coding: utf-8 -*-
from typing import Dict, Any, Optional
from loguru import logger
from langgraph.graph import StateGraph, END
from graph.state import AutoPulseState
from graph.nodes.input_parser import input_parser
from graph.nodes.search_dispatcher import search_dispatcher
from graph.nodes.api_collector import api_collector
from graph.nodes.crawler_collector import crawler_collector
from graph.nodes.data_merger import data_merger
from graph.nodes.sentiment_analyzer import sentiment_analyzer
from graph.nodes.hotspot_extractor import hotspot_extractor
from graph.nodes.major_opinion_detector import major_opinion_detector
from graph.nodes.volume_stats import volume_stats
from graph.nodes.fact_checker import fact_checker
from graph.nodes.report_generator import report_generator
from graph.nodes.response_formatter import response_formatter
from graph.nodes.dashboard_builder import dashboard_builder
from config import settings


def build_graph() -> StateGraph:
    graph = StateGraph(AutoPulseState)

    graph.add_node("input_parser", input_parser)
    graph.add_node("search_dispatcher", search_dispatcher)
    graph.add_node("api_collector", api_collector)
    graph.add_node("crawler_collector", crawler_collector)
    graph.add_node("data_merger", data_merger)
    graph.add_node("sentiment_analyzer", sentiment_analyzer)
    graph.add_node("hotspot_extractor", hotspot_extractor)
    graph.add_node("major_opinion_detector", major_opinion_detector)
    graph.add_node("calc_volume_stats", volume_stats)
    graph.add_node("fact_checker", fact_checker)
    graph.add_node("report_generator", report_generator)
    graph.add_node("response_formatter", response_formatter)
    graph.add_node("dashboard_builder", dashboard_builder)

    graph.set_entry_point("input_parser")
    graph.add_edge("input_parser", "search_dispatcher")
    graph.add_edge("search_dispatcher", "api_collector")
    graph.add_edge("api_collector", "crawler_collector")
    graph.add_edge("crawler_collector", "data_merger")
    graph.add_edge("data_merger", "sentiment_analyzer")
    graph.add_edge("sentiment_analyzer", "hotspot_extractor")
    graph.add_edge("hotspot_extractor", "major_opinion_detector")
    graph.add_edge("major_opinion_detector", "calc_volume_stats")
    graph.add_edge("calc_volume_stats", "fact_checker")
    graph.add_conditional_edges(
        "fact_checker",
        _fact_check_router,
        {
            "retry": "data_merger",
            "finish": "report_generator",
        },
    )
    graph.add_edge("report_generator", "response_formatter")
    graph.add_edge("response_formatter", "dashboard_builder")
    graph.add_edge("dashboard_builder", END)

    return graph


def _fact_check_router(state: AutoPulseState) -> str:
    if state.get("fact_check_passed", True):
        return "finish"
    iteration = state.get("iteration_count", 0)
    if iteration >= settings.RECURSION_LIMIT - 3:
        logger.warning(f"达到迭代上限，强制完成: iteration={iteration}")
        return "finish"
    return "retry"


def get_compiled_graph():
    graph = build_graph()
    return graph.compile()


def run_workflow(user_input: str, progress_callback=None) -> Dict[str, Any]:
    compiled = get_compiled_graph()
    initial_state = {
        "user_input": user_input,
        "car_model": "",
        "keywords": [],
        "intent": "",
        "focus_dimensions": [],
        "search_strategy": {},
        "selected_sources": [],
        "skipped_sources": [],
        "api_raw_data": [],
        "crawler_raw_data": [],
        "merged_data": [],
        "sentiment_results": [],
        "hotspot_keywords": [],
        "major_opinions": [],
        "alert_level": "none",
        "volume_stats": {},
        "fact_check_passed": False,
        "fact_check_errors": [],
        "quality_score": 0.0,
        "llm_suggestions": [],
        "insight_report": {},
        "agent_response": {},
        "dashboard_data": {},
        "iteration_count": 0,
        "error_messages": [],
        "progress": 0,
        "current_node": "",
    }

    config = {"recursion_limit": settings.RECURSION_LIMIT}

    try:
        result = compiled.invoke(initial_state, config=config)
        return result
    except Exception as e:
        logger.error(f"工作流执行失败: {e}")
        initial_state["error_messages"] = [str(e)]
        initial_state["dashboard_data"] = {
            "car_model": user_input,
            "total_count": 0,
            "sentiment_distribution": {"positive": 0, "negative": 0, "neutral": 0},
            "hotspot_keywords": [],
            "volume_stats": [],
            "time_trends": [],
            "details": [],
            "data_sufficient": False,
            "analysis_time": "",
            "error": str(e),
        }
        return initial_state
