## 1. 数据库与持久化层

- [x] 1.1 新增 conversations 表（id, title, created_at, updated_at）和 messages 表（id, conversation_id, role, content, message_type, metadata, created_at）到 db/init_db.py
- [x] 1.2 新增 db/conversation_db.py，实现会话 CRUD 和消息存储/查询方法
- [x] 1.3 验证数据库表自动创建和基本 CRUD 操作

## 2. Agent 主控层

- [x] 2.1 新增 agent/chat_agent.py，实现 ChatAgent 类：意图识别、对话管理、路由分发
- [x] 2.2 新增 agent/intent_recognizer.py，实现 LLM 意图识别（chat/query/visual_report/opinion_report/drill_down）+ 规则降级
- [x] 2.3 新增 agent/context_manager.py，实现上下文记忆：加载对话历史、维护当前车型、管理上下文窗口
- [x] 2.4 新增 agent/prompts.py，包含意图识别 prompt、对话回复 prompt、追问 prompt
- [x] 2.5 实现路由分发逻辑：chat→LLM直接回复，query→轻量分析+回复，visual_report→触发Workflow，opinion_report→触发Workflow，drill_down→上下文深入分析

## 3. SSE 流式通信

- [x] 3.1 新增 api/sse_stream.py，实现 SSE 流式推送工具（事件格式、心跳保活、断线处理）
- [x] 3.2 修改 app.py，新增 /api/chat SSE 端点，接收用户消息并流式返回 Agent 回复
- [x] 3.3 新增 /api/conversations 端点（会话列表）和 /api/conversations/<id>/messages 端点（消息历史）
- [x] 3.4 实现 Workflow 进度通过 SSE 推送

## 4. 可视化报告 Workflow

- [x] 4.1 新增 graph/workflows/visual_report_workflow.py，复用现有节点构建可视化报告 Workflow
- [x] 4.2 新增 graph/nodes/visual_report_renderer.py，将看板数据渲染为自包含 HTML（内联 ECharts/CSS）
- [x] 4.3 实现数据复用逻辑：上下文中已有分析结果时跳过数据采集
- [x] 4.4 验证可视化报告 HTML 可独立浏览且包含完整图表

## 5. 舆情报告 Workflow

- [x] 5.1 新增 report_templates/ 目录，创建日常监测、危机公关、品牌声誉三个 Markdown 模板
- [x] 5.2 新增 graph/workflows/opinion_report_workflow.py，实现舆情报告 Workflow
- [x] 5.3 新增 graph/nodes/report_template_selector.py，LLM 驱动的模板选择 + 规则降级
- [x] 5.4 新增 graph/nodes/report_chapter_generator.py，按模板结构逐章生成内容
- [x] 5.5 新增 graph/nodes/report_html_renderer.py，将章节内容渲染为结构化 HTML 报告（含目录、图表、预警高亮）
- [x] 5.6 实现防幻觉校验：章节内容中的数据引用与实际分析数据比对
- [x] 5.7 验证舆情报告 HTML 自包含且可独立浏览

## 6. 前端聊天界面

- [x] 6.1 重构 templates/index.html 为聊天界面布局（消息流、输入框、快速标签）
- [x] 6.2 新增 static/js/chat.js，实现聊天核心逻辑：SSE 连接、消息渲染、流式显示
- [x] 6.3 实现动态功能按钮渲染（📊可视化报告、📄舆情报告、🔍深入分析）
- [x] 6.4 实现 iframe 嵌入：可视化报告和舆情报告通过 iframe 嵌入聊天消息
- [x] 6.5 实现 iframe 自适应高度（postMessage 通信）
- [x] 6.6 新增 static/css/chat.css，聊天界面样式（消息气泡、按钮、iframe 容器）
- [x] 6.7 实现对话历史加载：页面刷新后从后端恢复最近会话
- [x] 6.8 实现快速标签点击发送消息

## 7. 集成与测试

- [ ] 7.1 集成 Agent 主控层 + SSE + 前端，验证端到端聊天流程
- [ ] 7.2 测试多轮对话：舆情查询→追问→生成报告
- [ ] 7.3 测试可视化报告 Workflow 端到端
- [ ] 7.4 测试舆情报告 Workflow 端到端
- [ ] 7.5 测试对话持久化：刷新页面后恢复历史
- [ ] 7.6 测试流式输出和进度反馈
- [ ] 7.7 测试意图识别降级（LLM 超时时的规则降级）
