## Module: event-brief + deep-report

事件简报（快速概览，30 秒）和深度报告（综合分析，1-3 分钟），均为推送后用户点击生成。

### Inputs
- 触发源：异常事件（anomaly_events）或用户主动请求
- 车型配置
- `analyzed_posts` 相关数据
- `heat_metrics` 相关数据
- 报告类型：`brief` | `deep`

### Outputs

**事件简报（brief）**：
- 事件概述（1-2 段）
- 关键数据点（声量变化、情感分布变化）
- 代表性帖子（3-5 条）
- 耗时：~30 秒

**深度报告（deep）**：
- 完整分析报告（2000-5000 字）
- 包含：背景概述、声量趋势分析、情感分析、事件解读、观点聚类、竞品对比（如配置）、建议
- 使用 LangGraph Research Agent（Reflection Loop）生成
- 耗时：1-3 分钟

### Behavior

**简报流程**：
1. 用户收到异常推送，点击"生成简报"
2. 从 `anomaly_events` + `analyzed_posts` 提取相关数据
3. 调用 DeepSeek-V4-Flash 单次生成简报
4. 展示在看板或推送卡片中

**深度报告流程**：
1. 用户收到异常推送或主动请求，点击"生成深度报告"
2. LangGraph Research Agent 启动：
   - Search Node：从本地数据库搜索相关帖子和指标数据
   - Summarize Node：生成阶段性摘要
   - Reflect Node：评估摘要是否充分，决定是否继续搜索
   - 循环 2-3 轮（Reflection Loop，参考 BettaFish）
3. 最终汇总为结构化报告
4. 展示在报告页面，支持下载

### LangGraph State（深度报告用）
```python
@dataclass
class ResearchState:
    vehicle_id: str
    event_context: str
    search_history: list[str]
    current_summary: str
    reflection_iteration: int
    max_iterations: int  # 默认 3
    final_report: str | None
```

### Interfaces
```python
# 后端 API
POST /api/report/brief
  body: { vehicle_id, anomaly_event_id? }
  response: SSE stream（简报内容）

POST /api/report/deep
  body: { vehicle_id, time_range?, anomaly_event_id? }
  response: SSE stream（进度 + 最终报告）

GET /api/reports/<vehicle_id>
  response: 历史报告列表
```
