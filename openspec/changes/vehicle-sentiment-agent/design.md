## Why

当前项目需要从旧版 AutoPulse 原型（单 Agent + 通用聊天框 + 单一 LLM）重构为全新的车型舆情全生命周期监控系统。经过充分的需求讨论和 brainstorming，已确定：双层架构（Pipeline + Agent）、双模型分工（Qwen3-4B + DeepSeek-V4-Flash）、四种输出形态（看板/简报/报告/锚点对话）、按需数据采集、3 个月历史数据、4 层热度指标体系、异常事件监测、多车型管理。技术选型：FastAPI + Vue 3 CDN + ECharts + Transformers/PEFT。

## What Changes

- **BREAKING**: 从单 Agent 聊天架构重构为 Pipeline + Agent 双层架构
- **BREAKING**: 后端从 Flask 切换到 FastAPI（原生异步支持）
- **BREAKING**: 前端从原生 JS 切换到 Vue 3 CDN + ECharts（组件化开发）
- 新增 Pipeline 层：数据采集 → 情感分析 → 事件打标 → 观点提取 → 入库（确定性流程）
- 新增 Agent 层：LangGraph Research Agent，用于事件深度分析和报告生成（Reflection Loop）
- 新增看板（Dashboard）：4 行 + 底部布局，Vue 3 组件化，支持锚点上下文对话
- 新增事件简报：异常事件快速概览，推送后用户点击生成
- 新增深度报告：综合分析报告，推送后用户点击生成
- 新增按需数据采集引擎：首次 3 个月历史 + 后续增量，gopup Cookie 通过 Playwright 自动获取
- 新增多车型管理：搜索/筛选/多选，生命周期锚点配置
- 新增 4 层热度指标体系：注意力指数 + 讨论声量 + 媒体声量 + 互动烈度
- 新增异常事件监测：24h 声量 ±60% vs 昨天触发告警
- 本地模型推理：Transformers + PEFT，先 API 占位，微调后切换
- 旧代码（graph/、agent/、crawler/ 等）将被重构替代

## Capabilities

### New Capabilities

- `data-collection-engine`: 按需数据采集引擎 —— 首次 3 个月历史 + 后续增量，gopup Cookie 通过 Playwright 自动获取，支持 7 个数据源
- `sentiment-analysis-pipeline`: 情感分析 Pipeline —— 文本级情感分类（positive/negative/neutral）+ 事件打标（5 大类）+ 观点标签提取（4 维度开放词表）
- `heat-metric-system`: 热度指标体系 —— 4 层指标计算（注意力指数/讨论声量/媒体声量/互动烈度）+ 时序聚合
- `anomaly-detector`: 异常事件监测 —— 24h 声量 ±60% 阈值检测 + 事件推送 + 去重
- `dashboard`: 舆情看板 —— 4 行 + 底部布局（概览/趋势/分析/异常与竞品/帖子详情表），Vue 3 组件化 + ECharts 可视化
- `anchor-context-dialog`: 看板锚点上下文对话 —— 点击图表元素弹出对话面板（Vue 3 组件），Generative UI 回复
- `event-brief`: 事件简报生成 —— 异常事件快速概览，30 秒内生成
- `deep-report`: 深度报告生成 —— 综合分析报告，LangGraph Research Agent（Reflection Loop）驱动，1-3 分钟生成
- `vehicle-management`: 多车型管理 —— 搜索/筛选/多选，生命周期锚点配置（上市/改款/退市），竞品车型配置
- `dual-model-router`: 双模型路由 —— Qwen3-4B（本地，Transformers + PEFT，分类任务）+ DeepSeek-V4-Flash（API，生成任务）自动路由

### Modified Capabilities

- `database-schema`: 数据库重构 —— 新增车型管理表、采集状态表、热度指标表、异常事件表、报告存储表

## Impact

- **后端**: 从 Flask workflow.py 重构为 FastAPI Pipeline 层 + Agent 层，新增数据采集引擎、分析引擎、看板 API
- **前端**: 从聊天界面重构为 Vue 3 看板界面 + 锚点对话面板，ECharts 图表交互
- **数据库**: 新增 5+ 张表，重构现有表结构
- **依赖**: 新增 gopup、MediaCrawler、FastAPI、Vue 3 CDN，保留 LangGraph
- **模型**: 新增本地 Qwen3-4B（Transformers + PEFT）推理，保留 DeepSeek-V4-Flash API
- **旧代码**: graph/、agent/、crawler/、collectors/ 等目录将被重构或替换
