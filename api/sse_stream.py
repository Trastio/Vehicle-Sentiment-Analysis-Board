# -*- coding: utf-8 -*-
import json
import time
from typing import Dict, Any, Generator
from loguru import logger


def format_sse_event(event_type: str, data: Dict[str, Any]) -> str:
    data.pop("html_content", None)
    payload = {"type": event_type, **data}
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def stream_response(generator: Generator[Dict[str, Any], None, None], conversation_id: str = "") -> Generator[str, None, None]:
    logger.info(f"[SSE] stream_response called, conv_id={conversation_id}")
    yield format_sse_event("connected", {"message": "连接已建立", "conversation_id": conversation_id})

    for event in generator:
        event_type = event.get("type", "text")
        logger.info(f"[SSE] event_type={event_type}, keys={list(event.keys())}")

        if event_type == "text":
            content = event.get("content", "")
            conversation_id = event.get("conversation_id", "")
            buttons = event.get("buttons", [])
            car_model = event.get("car_model", "")

            yield format_sse_event("text", {
                "content": content,
                "conversation_id": conversation_id,
                "buttons": buttons,
                "car_model": car_model,
            })

        elif event_type == "progress":
            yield format_sse_event("progress", {
                "content": event.get("content", "处理中..."),
            })

        elif event_type == "visual_report":
            report_url = event.get("report_url", "")
            conversation_id = event.get("conversation_id", "")
            car_model = event.get("car_model", "")
            content = event.get("content", "")
            logger.info(f"[SSE] visual_report: report_url={report_url}")

            yield format_sse_event("visual_report", {
                "content": content,
                "conversation_id": conversation_id,
                "car_model": car_model,
                "report_url": report_url,
            })

        elif event_type == "opinion_report":
            report_url = event.get("report_url", "")
            conversation_id = event.get("conversation_id", "")
            car_model = event.get("car_model", "")
            content = event.get("content", "")
            logger.info(f"[SSE] opinion_report: report_url={report_url}")

            yield format_sse_event("opinion_report", {
                "content": content,
                "conversation_id": conversation_id,
                "car_model": car_model,
                "report_url": report_url,
            })

        elif event_type == "error":
            yield format_sse_event("error", {
                "content": event.get("content", "发生错误"),
            })

    yield format_sse_event("done", {"message": "完成"})


def keepalive() -> str:
    return f": keepalive {int(time.time())}\n\n"
