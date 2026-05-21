## Module: anchor-context-dialog

看板锚点上下文对话，点击图表元素弹出 Vue 3 对话面板，Generative UI 回复。

### Inputs
- 锚点上下文：用户点击的图表类型 + 具体数据点（如"2026-05-20 的负面声量异常"）
- 对话历史（当前锚点下的历史消息）
- 车型配置

### Outputs
- 对话回复，采用 Generative UI 形式（Vue 3 组件动态渲染图表、表格、文本）
- 后续问题可追问

### Behavior
1. 用户点击看板图表元素
2. Vue 3 `DialogPanel` 组件侧边滑出，自动填充锚点上下文信息
3. 系统生成初始上下文摘要（如"你点击了 5 月 20 日的负面声量异常点，当天负面帖子 156 条，主要事件为..."）
4. 用户可追问（如"具体哪些负面帖子？"、"和竞品比怎么样？"）
5. 回复调用 DeepSeek-V4-Flash（SSE 流式），输入包含锚点上下文 + 对话历史 + 相关数据
6. 回复中的 Generative UI 指令由 Vue 3 动态组件渲染：
   - `text` → Markdown 渲染组件
   - `chart` → ECharts 图表组件
   - `table` → HTML 表格组件
   - `stat_cards` → 指标卡片组件
   - `post_list` → 帖子列表组件

### Context Injection
对话输入包含：
- 图表锚点信息（图表类型、时间范围、数据点值）
- 相关帖子样本（最多 20 条）
- 情感/事件/观点分布统计
- 生命周期阶段信息

### Interfaces
```python
# 后端 API（FastAPI，SSE StreamingResponse）
POST /api/dialog/anchor
  body: { vehicle_id, anchor_type, anchor_data, message, conversation_id? }
  response: SSE stream（对话回复 + Generative UI 指令）

GET /api/dialog/{conversation_id}/history
  response: 对话历史列表
```

### Generative UI Types
- `text`: Markdown 文本 → Vue 3 Markdown 渲染组件
- `chart`: ECharts 配置（JSON）→ Vue 3 ECharts 组件
- `table`: 表格数据 → Vue 3 HTML table 组件
- `stat_cards`: 指标卡片组 → Vue 3 卡片组件
- `post_list`: 帖子摘要列表 → Vue 3 列表组件
