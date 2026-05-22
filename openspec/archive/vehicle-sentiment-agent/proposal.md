## Context

目前项目存在旧版 AutoPulse 原型代码（基于 LangGraph 固定流水线 + 单一聊天界面），其架构设计与经过充分讨论后的新需求存在根本性差异：

1. **旧架构问题**：单 Agent + 单 LLM（DeepSeek-V4-Pro）、通用聊天框、无生命周期管理、无按需采集
2. **新架构需求**：双层架构（Pipeline + Agent）、双模型分工（本地 Qwen3-4B + API DeepSeek-V4-Flash）、看板锚点对话（非通用聊天框）、车型生命周期管理、按需数据采集

旧代码的 `openspec/changes/agent-chat-architecture/` 和 `docs/superpowers/` 均基于旧架构，需要用全新的设计替代。

技术栈约束：
- 后端：Python + FastAPI + LangGraph + SQLite
- 本地模型：Qwen3-4B-Instruct-2507 + Transformers + PEFT（LoRA 微调，RTX 4080 12GB VRAM）
- API 模型：DeepSeek-V4-Flash（报告生成/对话交互/复杂分析）
- 前端：Vue 3 CDN + ECharts
- 数据采集：gopup（Playwright 自动获取百度 Cookie）+ MediaCrawler + Tavily/Bocha/Anspire
- 工具链：Git + Superpowers

## Goals / Non-Goals

**Goals:**
- 构建车型舆情全生命周期监控系统（上市/改款/退市 3 个时间锚点）
- 实现四种输出形态：看板（Dashboard）、事件简报、深度报告、看板锚点上下文对话
- 实现双层架构：Pipeline 层（确定性数据流）+ Agent 层（LangGraph Research Agent，用于复杂事件分析）
- 实现双模型分工：Qwen3-4B（本地，情感分类+事件打标+观点提取）+ DeepSeek-V4-Flash（API，报告生成/对话交互）
- 实现按需数据采集：用户打开 Agent 时触发，首次拉 3 个月历史，后续增量
- 实现 4 层热度指标体系：注意力指数 + 讨论声量 + 媒体声量 + 互动烈度
- 实现异常事件监测：24h 声量 ±60% vs 昨天
- 实现多车型管理：搜索/筛选/多选，竞品车型由用户配置

**Non-Goals:**
- 不做用户认证/权限系统（单用户模式）
- 不做后台定时采集任务（按需触发）
- 不做 PDF/Word 导出（后续迭代）
- 不做 aspect-level 情感分析（用观点标签替代）
- 不做通用聊天框（只做看板锚点上下文对话）
- 本阶段不做微调（微调方案暂时搁置，先用 DeepSeek-V4-Flash 替代分析）

## Decisions

### Decision 1: 双层架构 —— Pipeline + Agent

**选择**: Pipeline 层处理确定性数据流（采集→分析→入库），Agent 层处理复杂任务（事件深度分析、报告生成）

**理由**:
- 数据采集和分析是确定性的流水线，不需要 Agent 的灵活推理
- 复杂事件分析需要搜索→总结→反思→再搜索的 Reflection Loop（参考 BettaFish）
- 分层后 Pipeline 可独立运行和测试，Agent 按需触发

**替代方案**:
- 纯 LangGraph：所有节点都是 Agent 节点，过于复杂，确定性任务效率低
- 纯 Pipeline：无法处理需要反思迭代的复杂分析任务

### Decision 2: 看板锚点对话（方向 2）而非通用聊天框

**选择**: 用户点击看板图表元素 → 弹出上下文对话面板 → Generative UI 回复

**理由**:
- 上下文明确（知道用户点了哪个数据点），回复质量更高
- 避免通用聊天框的"不知道该问什么"问题
- Generative UI 可直接展示图表、表格等结构化内容

**替代方案**:
- 通用聊天框：缺乏上下文，容易沦为无所不聊的闲聊

### Decision 3: 双模型分工

**选择**: Qwen3-4B-Instruct-2507（本地，Transformers + PEFT）+ DeepSeek-V4-Flash（API）

**理由**:
- 小模型负责高频分类任务（情感/事件/观点），本地运行零成本，延迟低
- 大模型负责低频生成任务（报告/对话），API 按量付费（1 元/百万 tokens），效果好
- 12GB VRAM 足以运行 Qwen3-4B FP16 + LoRA
- PEFT 原生支持 LoRA 加载，微调后切换只需改一行 model_path

**替代方案**:
- vLLM 推理服务：单用户场景 batching 优势用不上，12GB VRAM 偏紧
- llama.cpp GGUF：4B 模型不需要量化，LoRA 集成不如 PEFT 成熟

### Decision 4: 按需采集，不做后台定时任务

**选择**: 用户打开 Agent 时触发采集

**理由**:
- 单用户模式，无人访问时采集浪费资源
- 首次使用拉 3 个月历史数据覆盖大部分需求
- 后续增量采集，只拉新数据，效率高

### Decision 5: 车型生命周期只分 3 个锚点

**选择**: 上市、改款、退市

**理由**:
- 汽车行业实际节奏：新车上市（声量爆发）、改款（舆情转折）、退市（停止监控）
- 不需要更细的阶段划分（如预售、试驾期等），那些是事件而非阶段

### Decision 6: 事件简报与深度报告均为推送+点击生成

**选择**: 异常检测触发推送 → 用户点击 → 生成简报或报告

**理由**:
- 报告生成耗时（1-3 分钟），不应自动阻塞
- 用户决定是否需要深度分析，避免资源浪费
- 简报快速概览（30 秒），报告深度分析（1-3 分钟），用户按需选择

### Decision 7: 后端框架 FastAPI

**选择**: FastAPI 替代 Flask

**理由**:
- 原生 async/await，SSE 流式输出、MediaCrawler 异步采集、DeepSeek-V4-Flash 流式回复天然支持
- 自动生成 Swagger API 文档
- 旧代码本就要重构，无迁移成本

### Decision 8: 前端 Vue 3 CDN + ECharts

**选择**: Vue 3 CDN 单文件引入，不使用 Node.js 构建链

**理由**:
- 组件化开发看板卡片、对话面板、帖子表格，开发效率高 3-5 倍
- 响应式状态管理天然支持图表联动
- CDN 引入无需构建，满足轻量约束

### Decision 9: MediaCrawler 直接集成

**选择**: 作为项目子模块直接集成

**理由**:
- 复用其 30K+ star 的反爬策略和登录态管理
- 控制粒度细，可自定义搜索逻辑
- 32GB RAM 足以运行 Playwright

### Decision 10: gopup 百度 Cookie 通过 Playwright 自动获取

**选择**: 复用 MediaCrawler 的 Playwright 依赖，自动登录百度获取 Cookie

**理由**:
- 无需手动维护 Cookie，自动化程度高
- 复用已有 Playwright 依赖，不增加额外开销

## Risks / Trade-offs

- [Risk] 3 个月历史数据在部分平台（微博/抖音）覆盖不完整 → Mitigation: 新闻搜索补偿（微博热点必被新闻转载）
- [Risk] Qwen3-4B 微调前分类质量不稳定 → Mitigation: 先用 DeepSeek-V4-Flash 临时替代，微调后切换
- [Risk] 看板锚点对话交互实现复杂 → Mitigation: 先实现看板核心功能，对话功能迭代添加
- [Risk] 异常检测 ±60% 阈值可能不适用所有车型 → Mitigation: 先暂定，后续根据数据调整
- [Risk] 百度 Cookie 自动登录可能触发风控 → Mitigation: 控制登录频率，失败时 fallback 到手动配置
- [Trade-off] 暂不做微调 vs 立即微调：选择先搭建系统框架，用 API 替代小模型分析，微调后替换，降低初期复杂度
