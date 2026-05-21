## ADDED Requirements

### Requirement: 聊天界面布局
前端 SHALL 展示聊天界面，包含：消息流区域、输入框、发送按钮、快速标签。消息流 MUST 支持用户消息和 Agent 消息的区分显示。

#### Scenario: 初始页面加载
- **WHEN** 用户首次访问页面
- **THEN** 系统 SHALL 显示聊天界面，包含欢迎消息和快速标签（比亚迪秦PLUS、特斯拉Model 3等）

#### Scenario: 消息区分显示
- **WHEN** 对话中包含用户消息和 Agent 消息
- **THEN** 用户消息右对齐、Agent 消息左对齐，视觉上有明确区分

### Requirement: 动态功能按钮
Agent 消息中 SHALL 包含动态功能按钮，按钮由 Agent 根据上下文推荐，而非硬编码。按钮 MUST 包括：📊 查看可视化报告、📄 生成舆情报告、🔍 深入分析。

#### Scenario: 舆情查询后推荐按钮
- **WHEN** Agent 完成舆情查询回复
- **THEN** 消息底部 SHALL 显示 [📊 查看可视化报告] [📄 生成舆情报告] 按钮

#### Scenario: 点击功能按钮
- **WHEN** 用户点击 [📊 查看可视化报告] 按钮
- **THEN** 系统 SHALL 发送对应意图的消息给 Agent，触发可视化报告 Workflow

### Requirement: 可视化报告嵌入
可视化报告 SHALL 嵌入聊天消息中，使用 iframe 加载看板内容。iframe MUST 自适应高度，且与聊天页面样式隔离。

#### Scenario: 可视化报告嵌入显示
- **WHEN** visual-report-workflow 完成
- **THEN** 聊天消息中 SHALL 出现一个 iframe，内含完整的可视化看板（情感分布、热点词云、平台声量、时间趋势等）

#### Scenario: iframe 自适应高度
- **WHEN** 可视化报告 iframe 内容加载完成
- **THEN** iframe 高度 SHALL 自动调整为内容高度，无需用户手动滚动

### Requirement: 舆情报告嵌入
舆情报告 SHALL 嵌入聊天消息中，使用 iframe 加载 HTML 报告。报告 MUST 包含目录、章节、图表等结构化内容。

#### Scenario: 舆情报告嵌入显示
- **WHEN** opinion-report-workflow 完成
- **THEN** 聊天消息中 SHALL 出现一个 iframe，内含完整的结构化 HTML 舆情报告

### Requirement: 快速标签
前端 SHALL 保留快速标签功能，点击标签等同于输入对应车型的舆情查询。

#### Scenario: 点击快速标签
- **WHEN** 用户点击"比亚迪秦PLUS"快速标签
- **THEN** 系统 SHALL 自动发送"帮我分析比亚迪秦PLUS的舆情"消息

### Requirement: 流式消息显示
前端 SHALL 支持 SSE 流式消息的实时显示，Agent 回复 MUST 逐字出现，模拟打字效果。

#### Scenario: 流式文本显示
- **WHEN** 接收到 SSE 流式数据
- **THEN** Agent 消息 SHALL 逐字追加显示，有打字动画效果

#### Scenario: 进度消息显示
- **WHEN** 接收到 Workflow 进度消息
- **THEN** 消息区域 SHALL 显示进度提示（如"正在采集数据..."），完成后替换为最终结果

### Requirement: 对话历史加载
前端 SHALL 在页面加载时从后端加载最近的对话历史，用户 MUST 能看到之前的对话记录。

#### Scenario: 页面刷新后恢复
- **WHEN** 用户刷新页面
- **THEN** 聊天界面 SHALL 自动加载最近的对话历史，保持上下文连续
