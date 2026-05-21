## Context

当前 AutoPulse 是一个基于 LangGraph 的固定流水线系统，用户输入车型名后触发一条 13 节点的线性 Workflow，最终输出可视化看板。前端是传统的看板展示页面，无对话能力。

核心问题：
1. **无多轮对话**：用户只能输入车型名，无法追问、无法细化需求
2. **输出形式单一**：只有看板，无法按需生成舆情报告
3. **无意图理解**：系统不理解用户真正想问什么，只是机械执行全量分析
4. **无记忆**：每次查询独立，无法关联上下文

参考 BettaFish-main 的 ReportEngine 架构，其报告生成流程为：模板选择 → 文档布局 → 篇幅规划 → 章节生成 → IR 装订 → HTML 渲染，产出结构化的交互式 HTML 报告。

技术栈约束：
- 后端：Python + Flask + LangGraph + SQLite
- LLM：DeepSeek-V4-Pro（统一 API Key）
- 前端：原生 HTML/CSS/JS + ECharts + WordCloud
- 通信：SSE（流式）+ REST（数据）

## Goals / Non-Goals

**Goals:**
- 将前端从看板页面重构为聊天界面，支持多轮对话
- 实现 Agent 主控层：意图识别 → 对话管理 → 路由分发
- 实现可视化报告 Workflow，结果嵌入聊天消息
- 实现舆情报告 Workflow（参考 BettaFish），生成结构化 HTML 报告嵌入聊天
- 对话历史持久化到 SQLite
- 流式输出 Agent 回复
- 保留快速标签作为快捷入口

**Non-Goals:**
- 不实现用户认证/权限系统
- 不实现 PDF/Word 导出（后续迭代）
- 不实现多用户隔离（单用户模式）
- 不重构现有数据采集节点（复用即可）
- 不引入新的前端框架（保持原生 JS）

## Decisions

### Decision 1: Agent 主控层架构 —— 单 Agent + Workflow 混合

**选择**: 单 Agent 主控 + 两个 Workflow（可视化报告 / 舆情报告）

**理由**:
- 数据采集和分析是共享的，独立 Agent 会导致重复工作
- 单 Agent 更容易管理上下文和对话状态
- Workflow 复用现有节点，改造成本低

**替代方案**:
- 多 Agent 协作：过于复杂，当前规模不需要
- 纯 Workflow 无 Agent：无法实现多轮对话

**架构**:
```
用户消息 → Agent 主控（意图识别 + 上下文管理）
  ├── 闲聊/简单问答 → LLM 直接回复（流式）
  ├── 舆情查询 → 轻量分析 + 对话回复
  ├── 可视化报告 → 触发 visual-report-workflow → 嵌入看板
  └── 舆情报告 → 触发 opinion-report-workflow → 嵌入 HTML 报告
```

### Decision 2: 意图识别 —— LLM 分层路由

**选择**: 单次 LLM 调用识别意图 + 提取参数

**理由**:
- DeepSeek-V4-Pro 足够强大，单次调用可同时识别意图和提取参数
- 减少延迟，避免多轮 LLM 调用

**意图分类**:
- `chat`: 闲聊、问候、关于系统的问题
- `query`: 舆情查询（"帮我看看XX的舆情"）
- `visual_report`: 请求可视化报告（"生成可视化报告"、"看看数据"）
- `opinion_report`: 请求舆情报告（"生成舆情报告"、"出一份报告"）
- `drill_down`: 追问细节（"那条负面舆情具体说什么"）

### Decision 3: 前端通信 —— SSE 流式 + REST

**选择**: SSE（Server-Sent Events）用于流式回复，REST 用于数据查询

**理由**:
- SSE 比 WebSocket 更简单，天然支持流式文本
- 不需要双向通信（前端只需接收流式数据）
- Flask 原生支持 SSE，无需额外依赖

**替代方案**:
- WebSocket：功能过剩，实现复杂
- 长轮询：延迟高，体验差

### Decision 4: 舆情报告生成 —— 简化版 BettaFish 架构

**选择**: 模板选择 → 章节生成 → HTML 渲染（简化版，不含 IR 校验/篇幅规划）

**理由**:
- 完整 BettaFish 架构过于复杂（4个节点 + IR 校验 + 章节存储）
- 当前场景下报告结构相对固定，不需要动态篇幅规划
- 简化版仍保留核心：LLM 驱动的模板选择和章节内容生成

**报告模板**（参考 BettaFish）:
- 日常舆情监测报告
- 突发事件危机公关报告
- 企业品牌声誉分析报告

### Decision 5: 对话历史存储 —— SQLite

**选择**: 新增 conversations 和 messages 表

**理由**:
- 与现有 SQLite 架构一致，无需引入新数据库
- 对话数据量可控，SQLite 足够

### Decision 6: 可视化报告嵌入 —— iframe 沙箱

**选择**: 在聊天消息中嵌入 iframe，加载看板 HTML

**理由**:
- 看板包含 ECharts 图表，直接嵌入 DOM 会与聊天页面冲突
- iframe 提供样式隔离，避免 CSS 污染
- 通过 postMessage 通信，实现自适应高度

## Risks / Trade-offs

- [Risk] LLM 意图识别可能误判 → Mitigation: 设置默认路由为 query，误判时仍能提供基本服务
- [Risk] 舆情报告生成耗时较长（3-5分钟） → Mitigation: 流式进度反馈 + 异步生成 + 完成后推送
- [Risk] 前端重构工作量大 → Mitigation: 分阶段实施，先实现聊天核心，再逐步迁移看板功能
- [Risk] SSE 连接可能被代理/防火墙中断 → Mitigation: 心跳保活 + 断线重连机制
- [Trade-off] 简化版报告 vs 完整 BettaFish 架构：牺牲了动态篇幅规划和 IR 校验，换取更快的实现速度
