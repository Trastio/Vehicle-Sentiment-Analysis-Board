# -*- coding: utf-8 -*-
import os
import threading
import json
import time
from typing import Dict, Any
from datetime import datetime
from loguru import logger
from flask import Flask, render_template, request, jsonify, Response, stream_with_context, send_file
from config import settings
from db.init_db import init_database
from db.database import execute_query, execute_update
from db.conversation_db import (
    get_or_create_conversation, list_conversations, get_messages,
    add_message, update_conversation, get_conversation,
)
from api.sse_stream import stream_response
from graph.workflow import run_workflow

app = Flask(__name__)
app.config["SECRET_KEY"] = "autopulse-secret-key-2026"
app.config["JSON_AS_ASCII"] = False

_dashboard_cache: Dict[str, Dict[str, Any]] = {}
_monitor_lock = threading.Lock()


def _run_workflow_async(car_model: str):
    try:
        result = run_workflow(car_model)
        dashboard = result.get("dashboard_data", {})
        logger.info(f"工作流结果: car_model={car_model}, has_insight={'insight_report' in dashboard}")
        if dashboard and not dashboard.get("error"):
            with _monitor_lock:
                _dashboard_cache[car_model] = dashboard
            logger.info(f"工作流完成: {car_model}")
        else:
            error_msgs = result.get("error_messages", [])
            logger.error(f"工作流错误: {car_model}, {error_msgs}")
    except Exception as e:
        logger.error(f"工作流执行异常: {e}")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    user_message = data.get("message", "").strip()
    conversation_id = data.get("conversation_id", "")

    if not user_message:
        return jsonify({"error": "消息不能为空"}), 400

    conv = get_or_create_conversation(conversation_id)
    conversation_id = conv["id"]

    if not conv.get("title") or conv["title"] == "新对话":
        title = user_message[:30] + ("..." if len(user_message) > 30 else "")
        update_conversation(conversation_id, title=title)

    def generate():
        from agent.chat_agent import ChatAgent
        agent = ChatAgent()
        yield from stream_response(agent.process_message(conversation_id, user_message), conversation_id)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.route("/api/conversations")
def get_conversations():
    convs = list_conversations(limit=20)
    return jsonify({"conversations": convs})


@app.route("/api/conversations/<conv_id>/messages")
def get_conversation_messages(conv_id: str):
    messages = get_messages(conv_id, limit=100)
    return jsonify({"messages": messages})


@app.route("/api/conversations/<conv_id>")
def get_conv(conv_id: str):
    conv = get_conversation(conv_id)
    if conv:
        return jsonify(conv)
    return jsonify({"error": "会话不存在"}), 404


@app.route("/api/monitor", methods=["POST"])
def start_monitor():
    data = request.get_json(silent=True) or {}
    car_model = data.get("car_model", "").strip()
    if not car_model:
        return jsonify({"error": "车型名称不能为空"}), 400

    execute_update(
        "INSERT OR IGNORE INTO monitor_tasks (car_model, status, created_at) VALUES (?, 'active', ?)",
        (car_model, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    )

    thread = threading.Thread(target=_run_workflow_async, args=(car_model,), daemon=True)
    thread.start()

    return jsonify({"status": "started", "car_model": car_model})


@app.route("/api/monitor/<car_model>", methods=["DELETE"])
def stop_monitor(car_model: str):
    execute_update("UPDATE monitor_tasks SET status = 'stopped' WHERE car_model = ?", (car_model,))
    return jsonify({"status": "stopped", "car_model": car_model})


@app.route("/api/dashboard/<car_model>")
def get_dashboard(car_model: str):
    with _monitor_lock:
        data = _dashboard_cache.get(car_model)
    if data:
        return jsonify(data)
    return jsonify({"error": "暂无数据，请先启动监控"}), 404


@app.route("/api/details/<car_model>")
def get_details(car_model: str):
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 20, type=int)
    sentiment = request.args.get("sentiment", "")
    platform = request.args.get("platform", "")

    with _monitor_lock:
        cached = _dashboard_cache.get(car_model, {})

    details = cached.get("details", [])

    if sentiment:
        details = [d for d in details if d.get("sentiment_label") == sentiment]
    if platform:
        details = [d for d in details if d.get("platform") == platform]

    total = len(details)
    start = (page - 1) * page_size
    end = start + page_size
    paginated = details[start:end]

    return jsonify({
        "total": total,
        "page": page,
        "page_size": page_size,
        "details": paginated,
    })


@app.route("/api/crawl", methods=["POST"])
def manual_crawl():
    data = request.get_json(silent=True) or {}
    car_model = data.get("car_model", "").strip()
    if not car_model:
        return jsonify({"error": "车型名称不能为空"}), 400

    from crawler.platform_crawler import crawl_all_platforms
    try:
        result_count = len(crawl_all_platforms(car_model))
        return jsonify({"status": "success", "car_model": car_model, "count": result_count})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/monitors")
def list_monitors():
    rows = execute_query("SELECT * FROM monitor_tasks ORDER BY created_at DESC")
    return jsonify({"monitors": rows})


@app.route("/api/report/visual/<car_model>")
def get_visual_report(car_model: str):
    try:
        from graph.workflows.visual_report_workflow import generate_visual_report
        cached = _dashboard_cache.get(car_model)
        cached_dashboard = None
        if cached:
            cached_dashboard = cached
        html_content = generate_visual_report(car_model, cached_dashboard=cached_dashboard)
        return Response(html_content, mimetype="text/html")
    except Exception as e:
        logger.error(f"可视化报告生成失败: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/report/opinion/<car_model>")
def get_opinion_report(car_model: str):
    try:
        from graph.workflows.opinion_report_workflow import generate_opinion_report
        cached = _dashboard_cache.get(car_model)
        cached_dashboard = None
        if cached:
            cached_dashboard = cached
        html_content = generate_opinion_report(car_model, cached_dashboard=cached_dashboard)
        return Response(html_content, mimetype="text/html")
    except Exception as e:
        logger.error(f"舆情报告生成失败: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/report/file/<filename>")
def get_report_file(filename: str):
    reports_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")
    filepath = os.path.join(reports_dir, filename)
    if os.path.exists(filepath):
        return send_file(filepath, mimetype="text/html")
    return jsonify({"error": "报告文件不存在"}), 404


if __name__ == "__main__":
    init_database()
    logger.add(
        settings.LOG_DIR + "/autopulse_{time}.log",
        rotation="10 MB",
        retention="7 days",
        level="INFO",
    )
    logger.info("AutoPulse 汽车舆情监控系统启动")
    app.run(host=settings.HOST, port=settings.PORT, debug=False, threaded=True)
