# -*- coding: utf-8 -*-
import json
from datetime import datetime
from typing import Dict, Any, Optional, Callable
from loguru import logger
from graph.workflow import run_workflow


def generate_visual_report(car_model: str, progress_callback: Callable = None, cached_dashboard: Dict = None) -> str:
    if cached_dashboard:
        dashboard = cached_dashboard
    else:
        if progress_callback:
            progress_callback("正在采集并分析数据...")
        result = run_workflow(car_model)
        dashboard = result.get("dashboard_data", {})

    if progress_callback:
        progress_callback("正在渲染可视化报告...")

    html = _render_visual_html(dashboard)
    logger.info(f"可视化报告生成完成: {car_model}, HTML长度={len(html)}")
    return html


def _render_visual_html(data: Dict[str, Any]) -> str:
    car_model = data.get("car_model", "")
    total_count = data.get("total_count", 0)
    sentiment_dist = data.get("sentiment_distribution", {})
    hotspot_keywords = data.get("hotspot_keywords", [])
    volume_stats = data.get("volume_stats", [])
    time_trends = data.get("time_trends", [])
    major_opinions = data.get("major_opinions", [])
    alert_level = data.get("alert_level", "none")
    agent_response = data.get("agent_response", {})
    insight_report = data.get("insight_report", {})

    keyword_data = []
    for k in hotspot_keywords[:30]:
        if isinstance(k, dict):
            keyword_data.append({"name": k.get("word", str(k)), "value": k.get("weight", k.get("count", 10))})
        else:
            keyword_data.append({"name": str(k), "value": 10})

    sentiment_json = json.dumps(sentiment_dist, ensure_ascii=False)
    keyword_json = json.dumps(keyword_data, ensure_ascii=False)
    volume_json = json.dumps(volume_stats, ensure_ascii=False)
    trends_json = json.dumps(time_trends, ensure_ascii=False)

    alert_html = ""
    if major_opinions:
        alert_items = ""
        for op in major_opinions:
            level_class = "alert-critical" if op.get("alert_level") == "critical" else "alert-warning"
            alert_items += f"""
            <div class="alert-item {level_class}">
                <div class="alert-title">{_esc(op.get('title', ''))}</div>
                <div class="alert-content">{_esc(op.get('content', ''))}</div>
                <div class="alert-reason">{_esc(op.get('alert_reason', ''))}</div>
            </div>"""
        alert_html = f"""
        <div class="section alert-section">
            <h2>⚠️ 重大舆情预警</h2>
            {alert_items}
        </div>"""

    agent_html = ""
    if agent_response:
        key_points = ""
        for kp in agent_response.get("key_points", []):
            key_points += f"<li>{_esc(kp)}</li>"
        agent_html = f"""
        <div class="section agent-section">
            <h2>🤖 AI 分析摘要</h2>
            <div class="agent-conclusion">{_esc(agent_response.get('core_conclusion', ''))}</div>
            <ul class="agent-points">{key_points}</ul>
        </div>"""

    insight_html = ""
    if insight_report:
        insight_html = f"""
        <div class="section insight-section">
            <h2>💡 深度洞察</h2>
            <div class="insight-content">{_esc(insight_report.get('summary', ''))}</div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_esc(car_model)} - 可视化报告</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/echarts-wordcloud@2.1.0/dist/echarts-wordcloud.min.js"></script>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif; background: #0a0f1e; color: #e2e8f0; min-height: 100vh; }}
.top-bar {{ position: sticky; top: 0; z-index: 100; background: rgba(15, 23, 42, 0.92); backdrop-filter: blur(16px); border-bottom: 1px solid rgba(96, 165, 250, 0.12); padding: 12px 24px; display: flex; align-items: center; justify-content: space-between; }}
.top-bar-left {{ display: flex; align-items: center; gap: 12px; }}
.top-bar-logo {{ width: 32px; height: 32px; background: linear-gradient(135deg, #3b82f6, #8b5cf6); border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 14px; color: #fff; }}
.top-bar-title {{ font-size: 15px; font-weight: 600; color: #e2e8f0; }}
.top-bar-subtitle {{ font-size: 11px; color: #64748b; margin-top: 1px; }}
.top-bar-right {{ display: flex; align-items: center; gap: 10px; }}
.top-bar-btn {{ padding: 6px 14px; background: rgba(59, 130, 246, 0.1); border: 1px solid rgba(59, 130, 246, 0.2); border-radius: 8px; color: #60a5fa; font-size: 12px; font-weight: 500; cursor: pointer; transition: all 0.2s; display: flex; align-items: center; gap: 6px; text-decoration: none; }}
.top-bar-btn:hover {{ background: rgba(59, 130, 246, 0.2); border-color: rgba(59, 130, 246, 0.4); color: #93c5fd; }}
.container {{ max-width: 960px; margin: 0 auto; padding: 24px; }}
h1 {{ text-align: center; font-size: 22px; margin-bottom: 8px; background: linear-gradient(135deg, #60a5fa, #a78bfa); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }}
.report-time {{ text-align: center; font-size: 12px; color: #64748b; margin-bottom: 24px; }}
.section {{ background: #111827; border: 1px solid rgba(96, 165, 250, 0.08); border-radius: 14px; padding: 20px; margin-bottom: 20px; }}
h2 {{ font-size: 15px; color: #94a3b8; margin-bottom: 16px; border-bottom: 1px solid rgba(96, 165, 250, 0.1); padding-bottom: 10px; display: flex; align-items: center; gap: 8px; }}
.stats-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-bottom: 24px; }}
.stat-card {{ background: linear-gradient(135deg, #111827, #1a2332); border: 1px solid rgba(96, 165, 250, 0.08); border-radius: 14px; padding: 20px; text-align: center; transition: transform 0.2s, box-shadow 0.2s; }}
.stat-card:hover {{ transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.3); }}
.stat-value {{ font-size: 32px; font-weight: 700; }}
.stat-label {{ font-size: 12px; color: #64748b; margin-top: 4px; letter-spacing: 0.5px; }}
.stat-positive .stat-value {{ color: #4ade80; }}
.stat-negative .stat-value {{ color: #f87171; }}
.stat-neutral .stat-value {{ color: #fbbf24; }}
.chart-container {{ width: 100%; height: 300px; }}
.charts-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
.alert-section {{ border: 1px solid rgba(239,68,68,0.2); background: linear-gradient(135deg, #111827, #1a1020); }}
.alert-item {{ padding: 14px; margin-bottom: 10px; border-radius: 10px; background: rgba(0,0,0,0.3); }}
.alert-critical {{ border-left: 4px solid #ef4444; }}
.alert-warning {{ border-left: 4px solid #f59e0b; }}
.alert-title {{ font-weight: 600; color: #f87171; margin-bottom: 6px; font-size: 14px; }}
.alert-content {{ font-size: 13px; color: #cbd5e1; line-height: 1.6; }}
.alert-reason {{ font-size: 12px; color: #94a3b8; margin-top: 6px; padding-top: 6px; border-top: 1px solid rgba(255,255,255,0.05); }}
.agent-section {{ border: 1px solid rgba(96,165,250,0.15); background: linear-gradient(135deg, #111827, #0f1a2e); }}
.agent-conclusion {{ font-size: 15px; line-height: 1.8; margin-bottom: 14px; color: #e2e8f0; }}
.agent-points {{ padding-left: 20px; }}
.agent-points li {{ margin-bottom: 8px; line-height: 1.6; color: #cbd5e1; font-size: 13px; }}
.agent-points li::marker {{ color: #60a5fa; }}
.insight-section {{ border: 1px solid rgba(168,85,247,0.15); background: linear-gradient(135deg, #111827, #1a0f2e); }}
.insight-content {{ line-height: 1.8; color: #cbd5e1; font-size: 14px; }}
.footer {{ text-align: center; padding: 24px; font-size: 12px; color: #475569; border-top: 1px solid rgba(96,165,250,0.08); margin-top: 20px; }}
@media print {{
    .top-bar {{ position: static; background: #fff; color: #000; border-bottom: 2px solid #e2e8f0; }}
    .top-bar-title, .top-bar-subtitle {{ color: #000; }}
    .top-bar-btn {{ display: none; }}
    body {{ background: #fff; color: #1e293b; }}
    .section {{ background: #fff; border: 1px solid #e2e8f0; }}
    .stat-card {{ background: #f8fafc; border: 1px solid #e2e8f0; }}
    h1 {{ -webkit-text-fill-color: #1e40af; color: #1e40af; }}
    h2 {{ color: #334155; border-color: #e2e8f0; }}
}}
@media (max-width: 640px) {{
    .charts-row {{ grid-template-columns: 1fr; }}
    .stats-grid {{ grid-template-columns: 1fr; }}
    .container {{ padding: 12px; }}
    .top-bar {{ padding: 10px 14px; }}
}}
</style>
</head>
<body>
<div class="top-bar">
    <div class="top-bar-left">
        <div class="top-bar-logo">🚗</div>
        <div>
            <div class="top-bar-title">AutoPulse 可视化报告</div>
            <div class="top-bar-subtitle">{_esc(car_model)} 舆情数据看板</div>
        </div>
    </div>
    <div class="top-bar-right">
        <button class="top-bar-btn" onclick="window.print()">🖨️ 打印</button>
        <button class="top-bar-btn" onclick="window.close()">✕ 关闭</button>
    </div>
</div>
<div class="container">
<h1>📊 {_esc(car_model)} 舆情可视化报告</h1>
<div class="report-time">报告生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M")}</div>

<div class="stats-grid">
    <div class="stat-card stat-positive">
        <div class="stat-value">{sentiment_dist.get('positive', 0)}</div>
        <div class="stat-label">正面舆情</div>
    </div>
    <div class="stat-card stat-negative">
        <div class="stat-value">{sentiment_dist.get('negative', 0)}</div>
        <div class="stat-label">负面舆情</div>
    </div>
    <div class="stat-card stat-neutral">
        <div class="stat-value">{sentiment_dist.get('neutral', 0)}</div>
        <div class="stat-label">中性舆情</div>
    </div>
</div>

{agent_html}
{alert_html}

<div class="charts-row">
    <div class="section">
        <h2>📈 情感分布</h2>
        <div id="sentimentChart" class="chart-container"></div>
    </div>
    <div class="section">
        <h2>☁️ 热点词云</h2>
        <div id="keywordChart" class="chart-container"></div>
    </div>
</div>

<div class="charts-row">
    <div class="section">
        <h2>📊 平台声量</h2>
        <div id="volumeChart" class="chart-container"></div>
    </div>
    <div class="section">
        <h2>📉 时间趋势</h2>
        <div id="trendChart" class="chart-container"></div>
    </div>
</div>

{insight_html}

<div class="footer">AutoPulse 汽车舆情智能监控系统 | 本报告由AI辅助生成，数据仅供参考</div>
</div>

<script>
var sentimentData = {sentiment_json};
var keywordData = {keyword_json};
var volumeData = {volume_json};
var trendsData = {trends_json};

var sentimentChart = echarts.init(document.getElementById('sentimentChart'));
sentimentChart.setOption({{
    tooltip: {{ trigger: 'item' }},
    series: [{{
        type: 'pie', radius: ['40%', '70%'],
        data: [
            {{ value: sentimentData.positive || 0, name: '正面', itemStyle: {{ color: '#4ade80' }} }},
            {{ value: sentimentData.negative || 0, name: '负面', itemStyle: {{ color: '#f87171' }} }},
            {{ value: sentimentData.neutral || 0, name: '中性', itemStyle: {{ color: '#fbbf24' }} }}
        ],
        label: {{ color: '#e2e8f0' }}
    }}]
}});

var keywordChart = echarts.init(document.getElementById('keywordChart'));
keywordChart.setOption({{
    tooltip: {{}},
    series: [{{
        type: 'wordCloud',
        shape: 'circle',
        sizeRange: [12, 40],
        rotationRange: [-45, 45],
        gridSize: 8,
        textStyle: {{ color: function() {{ var colors = ['#60a5fa','#4ade80','#fbbf24','#f87171','#a78bfa']; return colors[Math.floor(Math.random()*colors.length)]; }} }},
        data: keywordData
    }}]
}});

var volumeChart = echarts.init(document.getElementById('volumeChart'));
var volNames = (volumeData || []).map(function(d) {{ return d.name || d.platform || ''; }});
var volValues = (volumeData || []).map(function(d) {{ return d.value || d.count || 0; }});
volumeChart.setOption({{
    tooltip: {{ trigger: 'axis' }},
    xAxis: {{ type: 'category', data: volNames, axisLabel: {{ color: '#94a3b8' }} }},
    yAxis: {{ type: 'value', axisLabel: {{ color: '#94a3b8' }} }},
    series: [{{ type: 'bar', data: volValues, itemStyle: {{ color: '#60a5fa' }} }}]
}});

var trendChart = echarts.init(document.getElementById('trendChart'));
var tDates = (trendsData || []).map(function(d) {{ return d.date || d.time || ''; }});
var tValues = (trendsData || []).map(function(d) {{ return d.count || d.value || 0; }});
trendChart.setOption({{
    tooltip: {{ trigger: 'axis' }},
    xAxis: {{ type: 'category', data: tDates, axisLabel: {{ color: '#94a3b8' }} }},
    yAxis: {{ type: 'value', axisLabel: {{ color: '#94a3b8' }} }},
    series: [{{ type: 'line', data: tValues, smooth: true, itemStyle: {{ color: '#4ade80' }}, areaStyle: {{ color: 'rgba(74,222,128,0.1)' }} }}]
}});

window.addEventListener('resize', function() {{
    sentimentChart.resize();
    keywordChart.resize();
    volumeChart.resize();
    trendChart.resize();
}});

try {{
    var height = document.body.scrollHeight;
    window.parent.postMessage({{ type: 'iframe-resize', height: height }}, '*');
}} catch(e) {{}}
</script>
</body>
</html>"""
    return html


def _esc(text: str) -> str:
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
