# -*- coding: utf-8 -*-
import json
import os
import threading
import queue
from typing import Dict, Any, Generator, Optional, Callable
from loguru import logger
from agent.intent_recognizer import recognize_intent
from agent.prompts import INTENT_CHAT, INTENT_QUERY, INTENT_VISUAL_REPORT, INTENT_OPINION_REPORT, INTENT_DRILL_DOWN
from agent.context_manager import ContextManager
from db.conversation_db import get_or_create_conversation, add_message, get_messages, update_conversation
from graph.llm_utils import call_llm_json

REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports")


SYSTEM_PROMPT_CHAT_AGENT = """你是 AutoPulse 汽车舆情智能监控助手。你专业、友好、高效。

你的核心能力：
1. 舆情查询：分析指定车型的舆情态势
2. 可视化报告：生成包含图表的可视化数据报告
3. 舆情报告：生成结构化的舆情分析报告
4. 深入分析：对特定舆情事件进行深入解读

对话规则：
- 基于实际分析数据回答，不要编造
- 如果用户没有指定车型，先询问
- 回复简洁专业，重点突出
- 适当推荐用户使用可视化报告或舆情报告功能获取更详细的分析
- 如果有重大预警，必须突出提醒"""

_dashboard_cache: Dict[str, Dict] = {}


class ChatAgent:
    def __init__(self):
        self.context_manager = ContextManager()

    def process_message(self, conversation_id: str, user_message: str, progress_callback: Callable = None) -> Generator[Dict[str, Any], None, None]:
        if not conversation_id:
            conv = get_or_create_conversation()
            conversation_id = conv["id"]

        context = self.context_manager.load_context(conversation_id)
        add_message(conversation_id, "user", user_message)
        self.context_manager.invalidate(conversation_id)

        intent_result = recognize_intent(user_message, context.get("messages", []))
        intent = intent_result["intent"]
        car_model = intent_result.get("car_model", "")

        if intent not in (INTENT_CHAT, INTENT_DRILL_DOWN) and not car_model:
            car_model = context.get("car_model", "")

        logger.info(f"意图识别: intent={intent}, car_model={car_model}, conv={conversation_id}")

        if car_model:
            self.context_manager.update_car_model(conversation_id, car_model)

        if not car_model and intent in (INTENT_QUERY, INTENT_VISUAL_REPORT, INTENT_OPINION_REPORT):
            reply = '请问您想了解哪个车型的舆情？请输入车型名称，如"比亚迪秦PLUS"、"特斯拉Model 3"等。'
            add_message(conversation_id, "assistant", reply, "text")
            yield {"type": "text", "content": reply, "conversation_id": conversation_id}
            return

        if intent == INTENT_CHAT:
            yield from self._handle_chat(conversation_id, user_message, context)
        elif intent == INTENT_QUERY:
            yield from self._handle_query(conversation_id, user_message, car_model, context, progress_callback)
        elif intent == INTENT_VISUAL_REPORT:
            yield from self._handle_visual_report(conversation_id, car_model, context, progress_callback)
        elif intent == INTENT_OPINION_REPORT:
            yield from self._handle_opinion_report(conversation_id, car_model, context, progress_callback)
        elif intent == INTENT_DRILL_DOWN:
            yield from self._handle_drill_down(conversation_id, user_message, car_model, context)
        else:
            yield from self._handle_query(conversation_id, user_message, car_model, context, progress_callback)

    def _handle_chat(self, conv_id: str, user_message: str, context: Dict) -> Generator:
        reply = self._generate_chat_reply(user_message, context)
        add_message(conv_id, "assistant", reply, "text")
        yield {"type": "text", "content": reply, "conversation_id": conv_id}

    def _handle_query(self, conv_id: str, user_message: str, car_model: str, context: Dict, progress_callback: Callable = None) -> Generator:
        yield {"type": "progress", "content": f"正在分析 {car_model} 的舆情数据..."}

        result_queue = queue.Queue()
        error_holder = [None]

        def _run():
            try:
                from graph.workflow import run_workflow
                result = run_workflow(car_model)
                result_queue.put(result)
            except Exception as e:
                error_holder[0] = e
                result_queue.put(None)

        worker = threading.Thread(target=_run, daemon=True)
        worker.start()

        step = 0
        while worker.is_alive():
            worker.join(timeout=5)
            step += 1
            progress_msgs = [
                f"正在采集 {car_model} 的舆情数据...",
                f"正在分析情感倾向...",
                f"正在提取热点关键词...",
                f"正在生成分析报告...",
                f"正在进行质量校验...",
                f"正在整合分析结果...",
            ]
            msg = progress_msgs[step % len(progress_msgs)]
            yield {"type": "progress", "content": msg}

        result = result_queue.get()

        if result is None:
            error_reply = f"分析 {car_model} 的舆情时遇到问题，请稍后重试。"
            add_message(conv_id, "assistant", error_reply, "error")
            yield {"type": "text", "content": error_reply, "conversation_id": conv_id}
            return

        dashboard = result.get("dashboard_data", {})
        _dashboard_cache[conv_id] = dashboard
        agent_response = dashboard.get("agent_response", {})
        major_opinions = dashboard.get("major_opinions", [])
        alert_level = dashboard.get("alert_level", "none")

        reply_parts = []
        if agent_response.get("greeting"):
            reply_parts.append(agent_response["greeting"])
        if agent_response.get("core_conclusion"):
            reply_parts.append(agent_response["core_conclusion"])
        if agent_response.get("key_points"):
            for kp in agent_response["key_points"]:
                reply_parts.append(f"• {kp}")
        if agent_response.get("alert_summary"):
            reply_parts.append(f"⚠️ {agent_response['alert_summary']}")

        reply = "\n".join(reply_parts)

        buttons = [
            {"label": "📊 查看可视化报告", "action": "visual_report"},
            {"label": "📄 生成舆情报告", "action": "opinion_report"},
        ]

        add_message(conv_id, "assistant", reply, "text", {"car_model": car_model, "dashboard_cached": True})

        yield {
            "type": "text",
            "content": reply,
            "conversation_id": conv_id,
            "buttons": buttons,
            "car_model": car_model,
        }

    def _handle_visual_report(self, conv_id: str, car_model: str, context: Dict, progress_callback: Callable = None) -> Generator:
        yield {"type": "progress", "content": f"正在生成 {car_model} 的可视化报告..."}

        cached_dashboard = _dashboard_cache.get(conv_id)
        result_queue = queue.Queue()

        def _run():
            try:
                from graph.workflows.visual_report_workflow import generate_visual_report
                html_content = generate_visual_report(car_model, cached_dashboard=cached_dashboard)
                result_queue.put(html_content)
            except Exception as e:
                logger.error(f"可视化报告生成失败: {e}")
                result_queue.put(None)

        worker = threading.Thread(target=_run, daemon=True)
        worker.start()

        step = 0
        while worker.is_alive():
            worker.join(timeout=5)
            step += 1
            yield {"type": "progress", "content": f"正在生成 {car_model} 的可视化报告...（步骤 {step}）"}

        html_content = result_queue.get()

        if html_content is None:
            error_reply = f"生成可视化报告时遇到问题，请稍后重试。"
            add_message(conv_id, "assistant", error_reply, "error")
            yield {"type": "text", "content": error_reply, "conversation_id": conv_id}
            return

        report_path = _save_report(conv_id, car_model, "visual", html_content)

        add_message(conv_id, "assistant", f"{car_model} 可视化报告已生成", "visual_report", {"report_path": report_path, "car_model": car_model})

        report_url = "/api/report/file/" + report_path if report_path else "/api/report/visual/" + car_model

        yield {
            "type": "visual_report",
            "content": f"📊 {car_model} 可视化报告已生成",
            "report_url": report_url,
            "conversation_id": conv_id,
            "car_model": car_model,
        }

    def _handle_opinion_report(self, conv_id: str, car_model: str, context: Dict, progress_callback: Callable = None) -> Generator:
        yield {"type": "progress", "content": f"正在生成 {car_model} 的舆情报告..."}

        cached_dashboard = _dashboard_cache.get(conv_id)
        result_queue = queue.Queue()

        def _run():
            try:
                from graph.workflows.opinion_report_workflow import generate_opinion_report
                html_content = generate_opinion_report(car_model, cached_dashboard=cached_dashboard)
                result_queue.put(html_content)
            except Exception as e:
                logger.error(f"舆情报告生成失败: {e}")
                result_queue.put(None)

        worker = threading.Thread(target=_run, daemon=True)
        worker.start()

        step = 0
        while worker.is_alive():
            worker.join(timeout=5)
            step += 1
            yield {"type": "progress", "content": f"正在生成 {car_model} 的舆情报告...（步骤 {step}）"}

        html_content = result_queue.get()

        if html_content is None:
            error_reply = f"生成舆情报告时遇到问题，请稍后重试。"
            add_message(conv_id, "assistant", error_reply, "error")
            yield {"type": "text", "content": error_reply, "conversation_id": conv_id}
            return

        report_path = _save_report(conv_id, car_model, "opinion", html_content)

        add_message(conv_id, "assistant", f"{car_model} 舆情报告已生成", "opinion_report", {"report_path": report_path, "car_model": car_model})

        report_url = "/api/report/file/" + report_path if report_path else "/api/report/opinion/" + car_model

        yield {
            "type": "opinion_report",
            "content": f"📄 {car_model} 舆情报告已生成",
            "report_url": report_url,
            "conversation_id": conv_id,
            "car_model": car_model,
        }

    def _handle_drill_down(self, conv_id: str, user_message: str, car_model: str, context: Dict) -> Generator:
        reply = self._generate_drill_down_reply(user_message, car_model, context)
        add_message(conv_id, "assistant", reply, "text", {"car_model": car_model})

        buttons = [
            {"label": "📊 查看可视化报告", "action": "visual_report"},
            {"label": "📄 生成舆情报告", "action": "opinion_report"},
        ]

        yield {
            "type": "text",
            "content": reply,
            "conversation_id": conv_id,
            "buttons": buttons,
            "car_model": car_model,
        }

    def _generate_chat_reply(self, user_message: str, context: Dict) -> str:
        try:
            from collectors import get_llm
            llm = get_llm()
            history = self.context_manager.get_messages_for_llm(context.get("conversation_id", ""))
            msgs = [{"role": "system", "content": SYSTEM_PROMPT_CHAT_AGENT}]
            for m in history[-6:]:
                msgs.append({"role": m["role"], "content": m["content"]})
            msgs.append({"role": "user", "content": user_message})

            from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
            lc_msgs = []
            for m in msgs:
                if m["role"] == "system":
                    lc_msgs.append(SystemMessage(content=m["content"]))
                elif m["role"] == "user":
                    lc_msgs.append(HumanMessage(content=m["content"]))
                else:
                    lc_msgs.append(AIMessage(content=m["content"]))

            response = llm.invoke(lc_msgs)
            return response.content
        except Exception as e:
            logger.error(f"LLM对话生成失败: {e}")
            if "你好" in user_message or "您好" in user_message:
                return "您好！我是 AutoPulse 汽车舆情智能助手。我可以帮您分析汽车舆情、生成可视化报告和舆情分析报告。请告诉我您想了解哪个车型的舆情？"
            return "我是 AutoPulse 汽车舆情智能助手，可以帮您分析车型舆情、生成报告。请问您想了解哪个车型？"

    def _generate_drill_down_reply(self, user_message: str, car_model: str, context: Dict) -> str:
        try:
            from collectors import get_llm
            llm = get_llm()
            history = self.context_manager.get_messages_for_llm(context.get("conversation_id", ""))

            prompt = f"""基于以下对话上下文，用户正在追问关于 {car_model} 的舆情细节。
请根据上下文给出专业、具体的回答。如果上下文中没有足够信息，请诚实说明并建议用户生成详细报告。

用户追问：{user_message}"""

            from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
            lc_msgs = [SystemMessage(content=SYSTEM_PROMPT_CHAT_AGENT)]
            for m in history[-6:]:
                if m["role"] == "user":
                    lc_msgs.append(HumanMessage(content=m["content"]))
                elif m["role"] == "assistant":
                    lc_msgs.append(AIMessage(content=m["content"]))
            lc_msgs.append(HumanMessage(content=prompt))

            response = llm.invoke(lc_msgs)
            return response.content
        except Exception as e:
            logger.error(f"追问回复生成失败: {e}")
            return f"关于 {car_model} 的详细信息，建议您点击「生成舆情报告」获取完整的分析报告。"


def _save_report(conv_id: str, car_model: str, report_type: str, html_content: str) -> str:
    os.makedirs(REPORTS_DIR, exist_ok=True)
    safe_model = car_model.replace(" ", "_").replace("/", "_")
    filename = f"{conv_id}_{safe_model}_{report_type}.html"
    filepath = os.path.join(REPORTS_DIR, filename)
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html_content)
        logger.info(f"报告已保存: {filepath}")
        return filename
    except Exception as e:
        logger.error(f"报告保存失败: {e}")
        return ""
