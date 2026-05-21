# -*- coding: utf-8 -*-
import os
import re
import json
from typing import Dict, Any, List, Callable, Optional
from datetime import datetime
from loguru import logger
from graph.workflow import run_workflow
from graph.llm_utils import call_llm_json

TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "report_templates")

TEMPLATE_MAP = {
    "daily_monitor": "daily_monitor.md",
    "crisis_report": "crisis_report.md",
    "brand_reputation": "brand_reputation.md",
}

SYSTEM_PROMPT_TEMPLATE_SELECTOR = """你是汽车舆情报告模板选择专家。根据舆情数据特征，选择最合适的报告模板。

可选模板：
- daily_monitor: 日常舆情监测报告，适用于常规监测，负面占比低于30%
- crisis_report: 突发事件危机公关报告，适用于存在重大负面事件、预警级别为critical的情况
- brand_reputation: 企业品牌声誉分析报告，适用于品牌综合评估

严格以JSON格式输出，不要输出其他内容：
{
    "template": "模板名称",
    "reasoning": "选择理由"
}"""

SYSTEM_PROMPT_CHAPTER_GENERATOR = """你是专业的汽车舆情分析师，正在撰写舆情报告。

要求：
1. 基于提供的实际数据进行分析，不得编造数据
2. 语言专业、客观、有逻辑
3. 每个章节内容充实，200-400字
4. 引用具体的数据和事实支撑观点
5. 如果数据不足，诚实说明并给出有限范围内的分析

严格以JSON格式输出，不要输出其他内容：
{
    "chapters": {
        "chapter_id_1": "章节1正文内容（支持Markdown格式）",
        "chapter_id_2": "章节2正文内容（支持Markdown格式）"
    }
}"""


def generate_opinion_report(car_model: str, progress_callback: Callable = None, cached_dashboard: Dict = None) -> str:
    if cached_dashboard:
        dashboard = cached_dashboard
    else:
        if progress_callback:
            progress_callback("正在采集并分析数据...")
        result = run_workflow(car_model)
        dashboard = result.get("dashboard_data", {})

    if progress_callback:
        progress_callback("正在选择报告模板...")

    template_name = _select_template(dashboard)
    template_content = _load_template(template_name)

    if progress_callback:
        progress_callback("正在生成报告章节...")

    chapters = _generate_chapters(car_model, template_content, dashboard)

    if progress_callback:
        progress_callback("正在渲染报告...")

    html = _render_report_html(car_model, template_name, template_content, chapters, dashboard)
    logger.info(f"舆情报告生成完成: {car_model}, 模板={template_name}, HTML长度={len(html)}")
    return html


def _select_template(data: Dict[str, Any]) -> str:
    alert_level = data.get("alert_level", "none")
    major_opinions = data.get("major_opinions", [])
    sentiment_dist = data.get("sentiment_distribution", {})
    total = sum(sentiment_dist.values()) if sentiment_dist else 0

    if alert_level == "critical" or len(major_opinions) >= 2:
        return "crisis_report"

    neg_count = sentiment_dist.get("negative", 0)
    neg_ratio = neg_count / total if total > 0 else 0
    if neg_ratio > 0.3:
        return "crisis_report"

    if total <= 50:
        logger.info(f"模板选择(快速): daily_monitor (数据量={total})")
        return "daily_monitor"

    try:
        context = f"预警级别: {alert_level}\n重大舆情数: {len(major_opinions)}\n负面占比: {neg_ratio:.1%}\n总声量: {total}"
        result = call_llm_json(SYSTEM_PROMPT_TEMPLATE_SELECTOR, context, fallback={"template": "daily_monitor", "reasoning": "降级选择"})
        template = result.get("template", "daily_monitor")
        if template in TEMPLATE_MAP:
            return template
    except Exception as e:
        logger.warning(f"LLM模板选择失败: {e}")

    return "daily_monitor"


def _load_template(template_name: str) -> str:
    filename = TEMPLATE_MAP.get(template_name, "daily_monitor.md")
    filepath = os.path.join(TEMPLATES_DIR, filename)
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.error(f"模板加载失败: {e}")
        return "# 舆情报告\n\n## 一、总体态势\n{{chapter:overall}}\n\n## 二、建议\n{{chapter:suggestion}}"


def _generate_chapters(car_model: str, template: str, data: Dict[str, Any]) -> Dict[str, str]:
    chapter_pattern = re.compile(r"\{\{chapter:(\w+)\}\}")
    chapters_to_generate = chapter_pattern.findall(template)

    if not chapters_to_generate:
        return {}

    data_context = _build_data_context(car_model, data)

    chapter_titles = []
    for chapter_id in chapters_to_generate:
        title = _get_chapter_title(chapter_id, template)
        chapter_titles.append(f"- {chapter_id}: {title}")

    prompt = f"""车型: {car_model}

需要生成的章节：
{chr(10).join(chapter_titles)}

数据上下文:
{data_context}"""

    fallback = {}
    for chapter_id in chapters_to_generate:
        title = _get_chapter_title(chapter_id, template)
        fallback[chapter_id] = f"数据不足，暂无法生成{title}的详细分析。"

    result = call_llm_json(
        SYSTEM_PROMPT_CHAPTER_GENERATOR,
        prompt,
        fallback={"chapters": fallback},
    )

    chapters = result.get("chapters", {})
    if not chapters:
        chapters = fallback

    for chapter_id in chapters_to_generate:
        if chapter_id not in chapters:
            title = _get_chapter_title(chapter_id, template)
            chapters[chapter_id] = f"数据不足，暂无法生成{title}的详细分析。"

    return chapters


def _get_chapter_title(chapter_id: str, template: str) -> str:
    lines = template.split("\n")
    for i, line in enumerate(lines):
        if f"{{{{chapter:{chapter_id}}}}}" in line:
            if i > 0:
                prev = lines[i - 1].strip()
                if prev.startswith("##"):
                    return prev.lstrip("#").strip()
    return chapter_id


def _build_data_context(car_model: str, data: Dict[str, Any]) -> str:
    parts = [f"车型: {car_model}"]

    sentiment_dist = data.get("sentiment_distribution", {})
    total = sum(sentiment_dist.values()) if sentiment_dist else 0
    parts.append(f"总声量: {total}")
    parts.append(f"正面: {sentiment_dist.get('positive', 0)}, 负面: {sentiment_dist.get('negative', 0)}, 中性: {sentiment_dist.get('neutral', 0)}")

    hotspot_keywords = data.get("hotspot_keywords", [])
    kw_strs = []
    for k in hotspot_keywords[:10]:
        if isinstance(k, dict):
            kw_strs.append(k.get("word", str(k)))
        else:
            kw_strs.append(str(k))
    parts.append(f"热点关键词: {', '.join(kw_strs)}")

    volume_stats = data.get("volume_stats", [])
    if volume_stats:
        vol_strs = []
        for v in volume_stats[:5]:
            if isinstance(v, dict):
                vol_strs.append(f"{v.get('name', v.get('platform', ''))}: {v.get('value', v.get('count', 0))}")
        parts.append(f"平台声量: {', '.join(vol_strs)}")

    major_opinions = data.get("major_opinions", [])
    if major_opinions:
        parts.append(f"重大舆情数: {len(major_opinions)}")
        for op in major_opinions[:3]:
            parts.append(f"  - {op.get('title', '')}: {op.get('content', '')[:50]}")

    alert_level = data.get("alert_level", "none")
    parts.append(f"预警级别: {alert_level}")

    agent_response = data.get("agent_response", {})
    if agent_response.get("core_conclusion"):
        parts.append(f"核心结论: {agent_response['core_conclusion']}")

    insight_report = data.get("insight_report", {})
    if insight_report.get("summary"):
        parts.append(f"洞察摘要: {insight_report['summary']}")

    return "\n".join(parts)


def _render_report_html(car_model: str, template_name: str, template: str, chapters: Dict[str, str], data: Dict[str, Any]) -> str:
    try:
        import markdown
    except ImportError:
        markdown = None

    chapter_pattern = re.compile(r"\{\{chapter:(\w+)\}\}")
    filled_template = chapter_pattern.sub(lambda m: chapters.get(m.group(1), ""), template)

    filled_template = filled_template.replace("{{car_model}}", _esc(car_model))
    filled_template = filled_template.replace("{{time_range}}", "最近7天")
    filled_template = filled_template.replace("{{report_time}}", datetime.now().strftime("%Y-%m-%d %H:%M"))
    filled_template = filled_template.replace("{{alert_level}}", data.get("alert_level", "none"))

    if markdown:
        body_html = markdown.markdown(filled_template, extensions=["tables", "toc"])
    else:
        body_html = _simple_markdown_to_html(filled_template)

    template_title = {
        "daily_monitor": "日常舆情监测报告",
        "crisis_report": "突发事件危机公关报告",
        "brand_reputation": "品牌声誉分析报告",
    }.get(template_name, "舆情分析报告")

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_esc(car_model)} - {template_title}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif; background: #f8fafc; color: #1e293b; line-height: 1.8; }}
.top-bar {{ position: sticky; top: 0; z-index: 100; background: rgba(255,255,255,0.95); backdrop-filter: blur(16px); border-bottom: 1px solid #e2e8f0; padding: 12px 24px; display: flex; align-items: center; justify-content: space-between; }}
.top-bar-left {{ display: flex; align-items: center; gap: 12px; }}
.top-bar-logo {{ width: 32px; height: 32px; background: linear-gradient(135deg, #3b82f6, #8b5cf6); border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 14px; color: #fff; }}
.top-bar-title {{ font-size: 15px; font-weight: 600; color: #0f172a; }}
.top-bar-subtitle {{ font-size: 11px; color: #64748b; margin-top: 1px; }}
.top-bar-right {{ display: flex; align-items: center; gap: 10px; }}
.top-bar-btn {{ padding: 6px 14px; background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px; color: #2563eb; font-size: 12px; font-weight: 500; cursor: pointer; transition: all 0.2s; display: flex; align-items: center; gap: 6px; text-decoration: none; }}
.top-bar-btn:hover {{ background: #dbeafe; border-color: #93c5fd; }}
.container {{ max-width: 820px; margin: 0 auto; padding: 40px 32px; }}
h1 {{ font-size: 26px; color: #0f172a; margin-bottom: 8px; border-bottom: 3px solid #3b82f6; padding-bottom: 12px; }}
h2 {{ font-size: 19px; color: #1e40af; margin-top: 32px; margin-bottom: 12px; padding-left: 12px; border-left: 4px solid #3b82f6; }}
h3 {{ font-size: 16px; color: #334155; margin-top: 20px; margin-bottom: 8px; }}
p {{ margin-bottom: 12px; color: #475569; font-size: 15px; }}
ul, ol {{ padding-left: 24px; margin-bottom: 12px; }}
li {{ margin-bottom: 6px; color: #475569; }}
strong {{ color: #0f172a; }}
.report-meta {{ background: linear-gradient(135deg, #eff6ff, #f5f3ff); border: 1px solid #e0e7ff; border-radius: 12px; padding: 18px 20px; margin-bottom: 28px; font-size: 14px; color: #475569; display: flex; flex-wrap: wrap; gap: 8px 24px; }}
.report-meta span {{ display: flex; align-items: center; gap: 4px; }}
.toc {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 18px 24px; margin-bottom: 32px; }}
.toc-title {{ font-weight: 600; color: #1e40af; margin-bottom: 10px; font-size: 14px; }}
.toc ul {{ list-style: none; padding-left: 0; }}
.toc li {{ padding: 5px 0; border-bottom: 1px solid #f1f5f9; }}
.toc li:last-child {{ border-bottom: none; }}
.toc a {{ color: #3b82f6; text-decoration: none; font-size: 14px; transition: color 0.2s; }}
.toc a:hover {{ text-decoration: underline; color: #1d4ed8; }}
.alert-box {{ background: #fef2f2; border: 1px solid #fecaca; border-radius: 12px; padding: 18px; margin: 16px 0; }}
.alert-box.warning {{ background: #fffbeb; border-color: #fde68a; }}
.footer {{ margin-top: 48px; padding-top: 20px; border-top: 2px solid #e2e8f0; font-size: 12px; color: #94a3b8; text-align: center; }}
@media print {{
    .top-bar {{ position: static; }}
    .top-bar-btn {{ display: none; }}
    body {{ background: #fff; }}
    .container {{ padding: 20px; }}
}}
@media (max-width: 640px) {{
    .container {{ padding: 16px; }}
    h1 {{ font-size: 20px; }}
    h2 {{ font-size: 16px; }}
    .top-bar {{ padding: 10px 14px; }}
    .report-meta {{ flex-direction: column; gap: 4px; }}
}}
</style>
</head>
<body>
<div class="top-bar">
    <div class="top-bar-left">
        <div class="top-bar-logo">🚗</div>
        <div>
            <div class="top-bar-title">AutoPulse 舆情报告</div>
            <div class="top-bar-subtitle">{_esc(car_model)} {template_title}</div>
        </div>
    </div>
    <div class="top-bar-right">
        <button class="top-bar-btn" onclick="window.print()">🖨️ 打印</button>
        <button class="top-bar-btn" onclick="window.close()">✕ 关闭</button>
    </div>
</div>
<div class="container">
<h1>{_esc(car_model)} {template_title}</h1>
<div class="report-meta">
<span>📅 报告时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}</span>
<span>📡 数据来源：微博、懂车帝、汽车之家、百度贴吧</span>
</div>
{body_html}
<div class="footer">AutoPulse 汽车舆情智能监控系统 | 本报告由AI辅助生成，数据仅供参考</div>
</div>
<script>
try {{
    var height = document.body.scrollHeight;
    window.parent.postMessage({{ type: 'iframe-resize', height: height }}, '*');
}} catch(e) {{}}
</script>
</body>
</html>"""
    return html


def _simple_markdown_to_html(text: str) -> str:
    lines = text.split("\n")
    html_lines = []
    in_list = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("# "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<h1>{_esc(stripped[2:])}</h1>")
        elif stripped.startswith("## "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<h2>{_esc(stripped[3:])}</h2>")
        elif stripped.startswith("### "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<h3>{_esc(stripped[4:])}</h3>")
        elif stripped.startswith("- "):
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            html_lines.append(f"<li>{_esc(stripped[2:])}</li>")
        elif stripped:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<p>{_esc(stripped)}</p>")
        else:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
    if in_list:
        html_lines.append("</ul>")
    return "\n".join(html_lines)


def _esc(text: str) -> str:
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
