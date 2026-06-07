## Why

当前 AutoPulse 是一个"一键触发 → 固定流水线 → 展示看板"的工具，而非真正的 AI Agent。它缺乏多轮对话能力、无法按需生成不同形式的输出（对话回复/可视化报告/舆情报告），用户只能被动接收全量结果。用户需要一个能像专业舆情顾问一样交互的智能体——通过聊天界面自然沟通，按需提供不同深度的分析成果。

## What Changes

- **BREAKING**: 将前端从"看板页面"重构为"聊天界面 + 动态功能按钮"，看板和报告嵌入聊天消息中
- 新增 Agent 主控层：LLM 意图识别 → 对话管理 → 路由分发（对话回复 / 可视化报告 / 舆情报告）
- 新增多轮对话支持：会话管理、上下文记忆、对话历史持久化到数据库
- 新增可视化报告 Workflow：数据采集 → 分析 → 看板渲染，结果嵌入聊天消息
- 新增舆情报告 Workflow：参考 BettaFish ReportEngine 架构，数据采集 → 分析 → 模板选择 → 章节生成 → HTML 渲染，结果嵌入聊天消息
- 新增流式输出：Agent 回复采用 SSE 逐字推送，长时间 Workflow 给出进度反馈
- 保留快速标签功能，作为聊天界面的快捷入口
- 保留现有数据采集、情感分析、热点提取等核心节点，作为 Workflow 的共享组件

## Capabilities

### New Capabilities
- `chat-agent`: Agent 主控层——意图识别、对话管理、路由分发、上下文记忆、流式回复
- `chat-frontend`: 聊天界面——消息流、动态功能按钮、可视化报告嵌入、舆情报告嵌入、快速标签
- `visual-report-workflow`: 可视化报告 Workflow——触发数据采集分析，生成嵌入聊天的看板
- `opinion-report-workflow`: 舆情报告 Workflow——参考 BettaFish 架构，生成结构化 HTML 舆情报告
- `conversation-persistence`: 对话持久化——会话管理、消息存储、上下文记忆

### Modified Capabilities

## Impact

- **前端**: 从 index.html 看板页面重构为聊天界面，dashboard.js 改为 chat.js
- **后端**: app.py 从 REST+SocketIO 改为 SSE 流式 + REST 混合架构
- **数据库**: 新增 conversations、messages 表
- **工作流**: 现有 workflow.py 保留为 visual-report-workflow，新增 opinion-report-workflow
- **依赖**: 新增 SSE 相关库（flask-sse 或手动实现）
- **API**: 新增 /api/chat、/api/conversations 等端点，保留 /api/monitor 兼容
